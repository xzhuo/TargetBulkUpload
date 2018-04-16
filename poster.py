import json
import requests
import logging
import bookdata
import sheetdata
import rowdata

TIMEOUT = 10
PROD_URL = "http://10.20.127.31:6474/db/data/cypher"
DEV_URL = "http://10.20.127.31:8474/db/data/cypher"


class Poster:
    def __init__(self, token, cypher, isupdate, is_production, meta_structure):
        self.token = token
        self.token_key = 'bearer ' + token
        self.neo4j_key = 'Basic ' + cypher
        self.isupdate = isupdate
        self.is_production = is_production
        self.meta_structure = meta_structure
        self.meta_url = self.meta_structure.action_url_meta
        self.submit_url = self.meta_structure.action_url_submit
        self.token_header = {"Authorization": self.token_key}
        self.cypher_header = {'accept': "application/json, text/plain, */*",
                              'x-stream': "true",
                              'content-type': "application/json;charset=utf-8",
                              'authorization': self.neo4j_key,
                              }
        if token != '':
            self.user_name = self.set_username()

    def set_username(self):
        ''' Set user name based on the token key. However, an error would occur if the token key is neo4j token'''
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

    def fetch_all_accession(self, sheet_name):
        """
        Using cypher query to query a list of {system_accession:value, user_accession:value, user:value} for a given sheet.
        Gonna replace the method fetch_all.
        """
        statement = "MATCH(sheet:{sheet_name}) WITH collect({system_accession:sheet.accession,user_accession:sheet.user_accession,user:sheet.user}) AS all_accession RETURN all_accession"
        if self.is_production:
            post_url = PROD_URL
        else:
            post_url = DEV_URL

        post_body = {"query": statement,
                     "params": {"sheet_name": sheet_name
                                },
                     "includeStats": "true"
                     }

        response = self._post(post_url, headers=self.cypher_header, data=json.dumps(post_body))
        return response['data']['row']

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

    def fetch_user_all(self, user):
        """
        send cypher query, get the json string, and convert to book_data. Download all records for a specific user.
        """
        meta_structure = self.meta_structure
        statement = "OPTIONAL MATCH (n)-[r]->(m) WHERE n.user={name} AND {tab} IN labels(n) RETURN distinct n as schema, collect({connection:coalesce(type(r),'na'),to:coalesce(labels(m),'na'),accession:coalesce(m.accession,'na')}) as added ORDER BY n.accession"
        no_relation_statment = "OPTIONAL MATCH (n) WHERE n.user={name} AND {tab} IN labels(n) AND NOT (n)-->() RETURN distinct n as schema, [] as added ORDER BY n.accession"
        if self.is_production:
            post_url = PROD_URL
        else:
            post_url = DEV_URL

        book_data = bookdata.BookData(meta_structure)
        for category, sheet_name in meta_structure.category_to_sheet_name.items():
            sheet_data = sheetdata.SheetData(sheet_name, meta_structure)
            book_data.add_sheet(sheet_data)
            logging.info("Fetching %s" % sheet_name)
            for user_statement in [statement, no_relation_statment]:
                post_body = {"query": user_statement,
                             "params": {"name": user,
                                        "tab": category
                                        },
                             "includeStats": "true"
                             }
                response = self._post(post_url, headers=self.cypher_header, data=json.dumps(post_body))

                # import ipdb; ipdb.set_trace()
                for data in response['data']:
                    if data[0] is not None:
                        record = rowdata.RowData(sheet_name, meta_structure)
                        record.schema = data[0]["data"]
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
                        for connection in data[1]:
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
            category = meta_structure.get_category(sheet_name)
            # print category
            # logging.info("fetching data in sheet %s!" % sheet_name)
            if category in whole_data:
                entry_list = whole_data[category]
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
            response = self._post(post_url, headers=self.token_header, data=post_body)

            # save the submission:
            if response["statusCode"] == 200:
                if "accession" in response:
                    row_data.schema["accession"] = response["accession"]
                    row_data.submission("submitted")
                    if is_production:
                        logging.info("successfully submitted record %s in %s to database as %s." % (user_accession, sheet_name, row_data.schema["accession"]))
                    else:
                        logging.info("successfully validated record %s in %s." % (user_accession, sheet_name))

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
                    existing_accession_set = set(existing_record.relationships[column_name][linkto_category][0])
                except:
                    print("Unable to get existing relationships of records %s in %s!" % (system_accession, sheet_name))
                # only change accession difference.
                to_add = list(new_accession_set - existing_accession_set)
                to_remove = list(existing_accession_set - new_accession_set)
                if to_add == [] and to_remove == []:
                    print("No change to relationship of records %s in %s!" % (system_accession, sheet_name))
                self.link_change(sheet_name, system_accession, linkto_category, to_remove, column_name, is_add=False)
                self.link_change(sheet_name, system_accession, linkto_category, to_add, column_name, is_add=True)

    def submit_link(self, row_data):
        sheet_name = row_data.sheet_name
        system_accession = row_data.schema["accession"]
        for column_name in row_data.relationships:
            for linkto_category in row_data.relationships[column_name]:
                accession_list = row_data.relationships[column_name][linkto_category]
                self.link_change(sheet_name, system_accession, linkto_category, accession_list, column_name, is_add=True)

    def link_change(self, sheet_name, system_accession, linkto_category, linkto_accession_list, connection_name, is_add):
        """
        direction is either "remove" or "add"
        """
        # Remove itself from linkto_list:
        if system_accession in linkto_accession_list:
            linkto_accession_list.remove(system_accession)

        if len(linkto_accession_list) > 0 and linkto_accession_list != ['']:  # skip empty accessions.
            if is_add:
                direction = "add"
            else:
                direction = "remove"
            meta_url, category, categories = self.get_sheet_info(sheet_name)
            linkurl = meta_url + '/api/' + categories + '/' + system_accession + '/' + linkto_category + '/' + direction  # direction should be add or remove
            link_body = {"connectionAcsn": linkto_accession_list, "connectionName": connection_name}
            response = self._post(linkurl, headers=self.token_header, data=json.dumps(link_body))

            if response["statusCode"] == 200:
                if is_add:
                    logging.info("successfully connected %s in %s to %s!" % (system_accession, sheet_name, linkto_accession_list))
                else:
                    logging.info("successfully removed relationship from %s in %s to %s!" % (system_accession, sheet_name, linkto_accession_list))
            else:
                logging.error("failed to connect %s in %s to %s!" % (system_accession, sheet_name, linkto_accession_list))
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
            submitted_response = self._post(saved_submission_url, headers=self.token_header, data=submission_body)

            if submitted_response["statusCode"] == 201:
                logging.info("Submission has been successfully saved as %s!" % submitted_response["submission_id"])
            else:
                logging.error("Fail to save submission!")

    def _post(self, url, headers, data, timeout=TIMEOUT):
        try:
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
            r.raise_for_status()
        except requests.exceptions.HTTPError as errh:
            logging.error("Http Error: %s" % errh)
        except requests.exceptions.ConnectionError as errc:
            logging.error("Error Connecting %s:" % errc)
        except requests.exceptions.Timeout as errt:
            logging.error("Timeout Error: %s" % errt)
        except requests.exceptions.RequestException as err:
            logging.error(err)
        response = r.json()
        return response
