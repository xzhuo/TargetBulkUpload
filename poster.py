class Poster:
    def __init__(self, token, meta_url, submit_url, isupdate, isproduction, meta_structure):
        self.token = token
        self.token_key = 'bearer ' + token
        self.meta_url = meta_url
        self.submit_url = submit_url
        self.isupdate = isupdate
        self.isproduction = isproduction
        self.meta_structure = meta_structure
        self.token_header = {"Authorization": self.token_key}
        self.user_name = self.set_username()

    def set_username(self):
        token_url = self.submit_url + '/api/usertoken/' + self.token
        return requests.get(token_url).json()["username"]

    def get_sheet_info(self, sheet_name):
        meta_url = self.meta_url
        category = self.meta_structure.get_category(sheet_name)
        categories = self.meta_structure.get_categories(sheet_name)
        return meta_url, category, categories

    def fetch_record(self, sheet_name, system_accession):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        get_url = meta_url + '/api/' + categories + '/' + system_accession
        main_obj = requests.get(get_url).json()["mainObj"]
        record = RowData(sheet_name, self.meta_structure)
        record.schema = main_obj[category]
        record.relationships = main_obj["added"]
        return record

    def fetch_all(self, sheet_name):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        user_name = self.user_name
        get_url = self.meta_url + '/api/' + categories
        response = requests.get(get_url).json()
        full_list = response[categories]  # returns a list of existing records.
        return [x for x in full_list if x['user'] == user_name]

    def submit_record(self, row_data):
        """
        The row_data is validated, but update, submit, test, isproduction are processed the same until now.
        submit or update record row_data to database. if it is not isproduction, replace accession with random string and submit.
        if isupdate:
            if no accession
                skip
            else
                update request
        else
            if no accession
                if isproduction
                    submit request
                else
                    replace user_accession
                    submit request
            else
                skip
        """
        isupdate = self.isupdate
        isproduction = self.isproduction
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
            if not isproduction:
                row_data.replace_accession()  # replace user accession with new random string, and save old accssion.
            post_url = meta_url + '/api/' + categories
            valid = 1
        else:
            logging.info("skip record %s %s in %s." %(accession, user_accession, sheet_name))

        if valid:
            post_body = row_data.schema
            accession = row_data.remove("accession")  # it is essentially a dict pop.
            response = requests.post(post_url, headers=self.token_header, data=post_body).json()

            if response['statusCode'] == 200:
                # save the submission:
                if "accession" in response:
                    row_data.schema["accession"] = response["accession"]
                    row_data.submission("submitted")
                    print("successfully submitted record %s in %s to database as %s." %(user_accession, sheet_name, row_data.schema["accession"]))
                else:
                    row_data.schema["accession"] = accession
                    row_data.submission("updated")
                    print("successfully updated record %s %s in %s." %(accession, user_accession, sheet_name))
            else:
                # should I sys.exit it, or just a warning with failed submission?
                sys.exit("post request of %s %s in %s failed!" %(accession, user_accession, sheet_name))

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
        if is_add:
            direction = "add"
        else:
             direction = "remove"
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        linkurl = meta_url + '/api/' + categories + '/' + system_accession + '/' + linkto_category + '/' + direction  # direction should be add or remove
        link_body = {"connectionAcsn": linkto_accession, "connectionName": connection_name}
        response = requests.post(linkurl, headers=self.token_header, data=link_body).json()
        if response["statusCode"] == 200:
            print("successfully connected %s in %s to %s!" % (system_accession, sheet_name, linkto_accession))
        else:
            print("failed to connect %s in %s to %s!" % (system_accession, sheet_name, linkto_accession))
            print(response["message"])

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
            submitted_response = requests.post(saved_submission_url, headers=self.token_header, data=submission_body).json()
            if submitted_response["statusCode"] == 201:
                logging.info("Submission has been successfully saved as %s!" % submitted_response["submission_id"])
            else:
                logging.error("Fail to save submission!")

    def duplication_check(self, sheet_data):
        """
        Make sure all the system accessions and user accessions are unique in the sheet.

        In the input sheet_data, each record has been validated.
        At least one of user or system accession exists, the other one must be "" if don't exists.

        If the record exists in the database, make sure both system and user accession match the record in the database.
        If there is only one accession in the sheet record, fetch and fill in the other accession from database.

        In the end, for records exist in database, both system and user accession must exist in the record;
        fo new records, only user accession in the record, system accession is ""
        """

        sheet_name = sheet_data.name
        existing_sheet_data = self.fetch_all(sheet_name)
        existing_user_accessions = [x['user_accession'] for x in existing_sheet_data]
        if len(existing_user_accessions) != len(set(existing_user_accessions)):
            sys.exit("redundant user accession exists in the %s, please contact dcc to fix the issue!" % sheet_name)
        existing_user_system_accession_pair = {x["user_accession"]: x["accession"] for x in existing_sheet_data}  # python2.7+
        existing_system_accessions = existing_user_system_accession_pair.values()
        # FIMXE user_accessions_in_sheet = Set(...)
        # system_accessions_in_sheet = Set(...)
        user_accession_list = []
        system_accession_list = []
        for record in sheet_data.all_records:
            accession = record.schema["accession"]
            user_accession = record.schema["user_accession"]
            """
            three possibilities:
            both user and system accession exist;
            system accession exists but user accession is "";
            system accession is "" but user accession exists.
            """
            if user_accession != "" and accession != "":
                if user_accession in existing_user_accessions and existing_user_system_accession_pair[user_accession] == accession:
                    if user_accession not in user_accession_list and accession not in system_accession_list:
                        user_accession_list.append(user_accession)
                        system_accession_list.append(accession)
                    else:
                        #FIXME instead of sys.exit,
                        # raise ValidationError("message"), then catch in main
                        sys.exit("redundant accession %s or %s in %s!" % (user_accession, accession, sheet_name))
                else:
                    sys.exit("accession %s or %s in %s does not match our database record!" % (user_accession, accession, sheet_name))
            elif user_accession == "" and accession != "":
                if accession in system_accession_list:
                    sys.exit("System accession %s in %s in invalid. It is a redundant accesion in the worksheet." % (accession, sheet_name))
                elif accession not in existing_system_accessions:
                    sys.exit("System accession %s in %s in invalid. It does not exist in the database." % (accession, sheet_name))
                else:
                    matching_user_accession = [k for k, v in existing_user_system_accession_pair.items() if v == accession][0]
                    user_accession_list.append(matching_user_accession)
                    system_accession_list.append(accession)
            elif user_accession != "" and accession == "":
                if user_accession in user_accession_list:
                    sys.exit("User accession %s in %s in invalid. It is a redundant accesion in the worksheet." % (user_accession, sheet_name))
                elif user_accession in existing_user_accessions:
                    matching_accession = existing_user_system_accession_pair[user_accession]
                    user_accession_list.append(user_accession)
                    system_accession_list.append(matching_accession)
                else:
                    user_accession_list.append(user_accession)
            else:
                raise Error("The code should never reach this point")
