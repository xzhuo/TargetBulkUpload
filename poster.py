import sys
import json
import requests
import logging

import bookdata
import sheetdata
import rowdata

TIMEOUT = 10


class Poster:
    def __init__(self, token, isupdate, is_production, meta_structure):
        self.token = token
        self.token_key = 'bearer ' + token
        self.isupdate = isupdate
        self.is_production = is_production
        self.meta_structure = meta_structure
        self.meta_url = self.meta_structure.action_url_meta
        self.submit_url = self.meta_structure.action_url_submit
        self.token_header = {"Authorization": self.token_key}
        if token != '':
            self.user_name = self.set_username()

    def set_username(self):
        token_url = self.submit_url + '/api/usertoken/' + self.token
        return requests.get(token_url, timeout=TIMEOUT).json()["username"]

    def get_sheet_info(self, sheet_name):
        meta_url = self.meta_url
        category = self.meta_structure.get_category(sheet_name)
        categories = self.meta_structure.get_categories(sheet_name)
        return meta_url, category, categories

    def fetch_record(self, sheet_name, system_accession):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        get_url = meta_url + '/api/' + categories + '/' + system_accession
        main_obj = requests.get(get_url, timeout=TIMEOUT).json()["mainObj"]
        record = rowdata.RowData(sheet_name, self.meta_structure)
        record.schema = main_obj[category]
        record.relationships = main_obj["added"]
        return record

    def fetch_all(self, sheet_name):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        user_name = self.user_name
        get_url = self.meta_url + '/api/' + categories
        response = requests.get(get_url, timeout=TIMEOUT).json()
        full_list = response[categories]  # returns a list of existing records.
        return [x for x in full_list if x['user'] == user_name]

    def read_cypher(self, json, sheet_name):
        """
        temporarily use the downloaded json file as input for now, return a book_data obj.
        """
        meta_structure = self.meta_structure
        book_data = bookdata.BookData(meta_structure)
        sheet_data = sheetdata.SheetData(sheet_name, meta_structure)
        book_data.add_sheet(sheet_data)
        for data in json['data']:
            record = rowdata.RowData(sheet_name, meta_structure)
            record.schema = data["row"][0]
            # initiate empty record relationship strcuture:
            for column_header in meta_structure.get_link_column_headers(sheet_name):
                # do link stuff
                column_name = meta_structure.get_column_name(sheet_name, column_header)
                sheetlinkto = meta_structure.get_linkto(sheet_name, column_header)
                categorylinkto = meta_structure.get_category(sheetlinkto)
                if column_name in record.relationships:
                    record.relationships[column_name][categorylinkto] = []
                else:
                    record.relationships[column_name] = {categorylinkto: []}
            for connection in data["row"][1]:
                record.relationships[connection['connection']][connection['to'][0]].append(connection['accession'])  # may change r, to m to more meaningful variable names.
            sheet_data.add_record(record)
        return book_data

    def fetch_submission(self, submission):
        """
        returns a workbook
        """

        meta_structure = self.meta_structure
        book_data = bookdata.BookData(meta_structure)
        entries_string = submission["details"]
        whole_data = json.loads(entries_string.replace("'", "\""))  # Gets a list of all accessions created for that object category
        for sheet_name in meta_structure.schema_dict.keys():
            sheet_data = sheetdata.SheetData(sheet_name, meta_structure)
            book_data.add_sheet(sheet_data)
            categories = meta_structure.get_categories(sheet_name)
            # print category
            # logging.info("fetching data in sheet %s!" % sheet_name)
            if categories in whole_data:
                entry_list = whole_data[categories]
                list_length = len(entry_list)
                for entry_count, entry in enumerate(entry_list):
                    logging.info("Got %d of %d records in sheet %s from database!" % (entry_count + 1, list_length, sheet_name))
                    # record = requests.get(action_url_meta + '/api/' + categories + '/' + entry).json().get('mainObj')
                    record_row = self.fetch_record(sheet_name, entry)  # A Rowdata obj.
                    sheet_data.add_record(record_row)
        return book_data

    def submit_record(self, row_data):
        """
        The row_data is validated, but update, submit, test, is_production are processed the same until now.
        submit or update record row_data to database. if it is not is_production, replace accession with random string and submit.
        if isupdate:
            if no accession
                skip
            else
                update request
        else
            if no accession
                if is_production
                    submit request
                else
                    replace user_accession
                    submit request
            else
                skip
        """
        isupdate = self.isupdate
        is_production = self.is_production
        sheet_name = row_data.sheet_name
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        accession = row_data.schema["accession"]
        user_accession = row_data.schema["user_accession"]
        valid = 0
        # for update, accession must exists, so it goes to else. for submit, accession must be "".
        if isupdate and accession != "":
            post_url = meta_url + '/api/' + categories + '/' + accession
            valid = 1
        elif (not isupdate) and accession == "":
            if not is_production:
                row_data.replace_accession()  # replace user accession with new random string, and save old accssion.
            post_url = meta_url + '/api/' + categories
            valid = 1
        else:
            logging.info("skip record %s %s in %s." % (accession, user_accession, sheet_name))

        if valid:
            post_body = row_data.schema
            accession = row_data.remove("accession")  # it is essentially a dict pop.
            try:
                r = requests.post(post_url, headers=self.token_header, data=post_body, timeout=TIMEOUT)
                r.raise_for_status()
            except requests.exceptions.HTTPError as errh:
                print("Http Error:", errh)
            except requests.exceptions.ConnectionError as errc:
                print("Error Connecting:", errc)
            except requests.exceptions.Timeout as errt:
                print("Timeout Error:", errt)
            except requests.exceptions.RequestException as err:
                print("post request of %s %s in %s failed!" % (accession, user_accession, sheet_name))
                print(err)

            response = r.json()

            # save the submission:
            if response["statusCode"] == 200:
                if "accession" in response:
                    row_data.schema["accession"] = response["accession"]
                    row_data.submission("submitted")
                    logging.info("successfully submitted record %s in %s to database as %s." % (user_accession, sheet_name, row_data.schema["accession"]))
                else:
                    row_data.schema["accession"] = accession
                    row_data.submission("updated")
                    logging.info("successfully updated record %s %s in %s." % (accession, user_accession, sheet_name))
            else:
                logging.error("post request of %s %s in %s failed!" % (accession, user_accession, sheet_name))
                logging.error(response["message"])

    def link_record(self, row_data):
        sheet_name = row_data.sheet_name
        system_accession = row_data.schema["accession"]
        if row_data.submission() == "updated":
            # fetch existing record:
            existing_record = self.fetch_record(sheet_name, system_accession)
            self.update_link(existing_record, row_data)
        if row_data.submission() == "submitted":
            self.submit_link(row_data)

    def update_link(self, existing_record, row_data):
        """
        Update the link if the link is different between existing_record and row_data.
        """
        sheet_name = row_data.sheet_name
        system_accession = row_data.schema["accession"]
        for column_name in row_data.relationships:
            for linkto_category in row_data.relationships[column_name]:
                new_accession_set = set(row_data.relationships[column_name][linkto_category])
                try:
                    existing_accession_set = set(existing_record.relationships[column_name][linkto_category])
                except:
                    print("unable to update different kinds of records %s in %s!" % (system_accession, sheet_name))
                # only change accession difference.
                to_remove = new_accession_set - existing_accession_set
                to_add = existing_accession_set - new_accession_set
                for linkto_accession in to_remove:
                    self.link_change(sheet_name, system_accession, linkto_category, linkto_accession, column_name, is_add=False)
                for linkto_accession in to_add:
                    self.link_change(sheet_name, system_accession, linkto_category, linkto_accession, column_name, is_add=True)

    def submit_link(self, row_data):
        sheet_name = row_data.sheet_name
        system_accession = row_data.schema["accession"]
        for column_name in row_data.relationships:
            for linkto_category in row_data.relationships[column_name]:
                accession_list = row_data.relationships[column_name][linkto_category]
                for linkto_accession in accession_list:
                    self.link_change(sheet_name, system_accession, linkto_category, linkto_accession, column_name, is_add=True)

    def link_change(self, sheet_name, system_accession, linkto_category, linkto_accession, connection_name, is_add):
        """
        direction is either "remove" or "add"
        """
        if linkto_accession != "":  # skip empty accessions.
            if is_add:
                direction = "add"
            else:
                direction = "remove"
            meta_url, category, categories = self.get_sheet_info(sheet_name)
            linkurl = meta_url + '/api/' + categories + '/' + system_accession + '/' + linkto_category + '/' + direction  # direction should be add or remove
            link_body = {"connectionAcsn": linkto_accession, "connectionName": connection_name}
            try:
                r = requests.post(linkurl, headers=self.token_header, data=link_body, timeout=TIMEOUT)
                r.raise_for_status()
            except requests.exceptions.HTTPError as errh:
                print("Http Error:", errh)
            except requests.exceptions.ConnectionError as errc:
                print("Error Connecting:", errc)
            except requests.exceptions.Timeout as errt:
                print("Timeout Error:", errt)
            except requests.exceptions.RequestException as err:
                print("failed to connect %s in %s to %s!" % (system_accession, sheet_name, linkto_accession))
                print(err)

            response = r.json()
            if response["statusCode"] == 200:
                logging.info("successfully connected %s in %s to %s!" % (system_accession, sheet_name, linkto_accession))
            else:
                logging.error("failed to connect %s in %s to %s!" % (system_accession, sheet_name, linkto_accession))
                logging.error(response["message"])

    def save_submission(self, book_data):
        isupdate = self.isupdate
        submission_log = dict()
        for sheet_name, sheet_data in book_data.data.items():
            category = self.meta_structure.get_category(sheet_name)
            accession_list = []
            for record in sheet_data.all_records:
                if (isupdate and record.submission() == "updated") or ((not isupdate) and record.submission() == "submitted"):
                    accession_list.append(record.schema["accession"])
            if len(accession_list) > 0:
                submission_log[category] = accession_list

        saved_submission_url = self.submit_url + "/api/submission"
        if bool(submission_log):  # Only save not empty submissions, and also save update submissions.
            submission_body = {"details": json.dumps(submission_log), "update": isupdate}
            try:
                r = requests.post(saved_submission_url, headers=self.token_header, data=submission_body, timeout=TIMEOUT)
                r.raise_for_status()
            except requests.exceptions.HTTPError as errh:
                print("Http Error:", errh)
            except requests.exceptions.ConnectionError as errc:
                print("Error Connecting:", errc)
            except requests.exceptions.Timeout as errt:
                print("Timeout Error:", errt)
            except requests.exceptions.RequestException as err:
                print(err)

            submitted_response = r.json()
            if submitted_response["statusCode"] == 201:
                logging.info("Submission has been successfully saved as %s!" % submitted_response["submission_id"])
            else:
                logging.error("Fail to save submission!")
