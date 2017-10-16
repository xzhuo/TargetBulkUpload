class RowData:
    def __init__(self, sheet_name, meta_structure):
        self.sheet_name = sheet_name
        self.meta_structure = meta_structure
        self.schema = dict()
        self.relationships = dict()

    def add(self, column_header, value):  # add or replace value in column
        sheet_name = self.sheet_name
        meta_structure = self.meta_structure
        column_name = meta_structure.get_column_name(sheet_name, column_header)
        if column_header in meta_structure.get_link_column_headers(sheet_name):
            # do link stuff
            accession_list = value.split(",")  # split value in cell by ",""
            sheetlinkto = meta_structure.get_linkto(self.sheet_name, column_header)
            categorylinkto = meta_structure.get_category(sheetlinkto)
            if column_name in self.relationships:
                self.relationships[column_name][categorylinkto] = accession_list
            else:
                self.relationships[column_name] = {categorylinkto: accession_list}
        elif column_header in meta_structure.get_schema_column_headers(sheet_name):
            self.schema[column_name] = value
        else:
            sys.exit("unknown column %s in %s!" % (column_header, sheet_name))

    def remove(self, column_name):
        """
        It's input is a column_name, instead of a column_header! And it only works for column names in schema. I use it only to delete accession columns.
        """
        if column_name in self.schema:
            return self.schema.pop(column_name)
        else:
            sys.exit("remove method can only delete schema columns, but you are trying to delete %s in %s" % (column_name, self.sheet_name))

    def old_accession(self, old_accession=""):
        # redundant with submission, but seems it is bad idea to make mutable attribes.
        if old_accession == "":
            try:
                return self.the_old_accession
            except:
                return ""
        else:
            self.the_old_accession = old_accession

    def submission(self, submission=""):
        """
        submission should be "submitted" or "updated"
        with param, set the submission;
        without param, returns current submission.
        """

        if submission == "":
            try:
                return self.the_submission
            except:
                return ""
        else:
            self.the_submission = submission

    def replace_accession(self, new_user_accession=""):
        sheet_name = self.sheet_name
        meta_structure = self.meta_structure
        user_accession_rule = meta_structure.get_user_accession_rule(sheet_name)
        if new_user_accession == "":
            randomid = uuid.uuid1()
            new_user_accession = user_accession_rule + str(randomid)
        self.old_accession(self.schema["user_accession"])
        self.schema["user_accession"] = new_user_accession

    def validate_add(self, column_header, cell_obj, datemode):
        """
        :param: column_header - the column_header of the cell you want to add.
        :param: cell_obj - the cell object from xrld package.
        :validate and add the cell value to the row_data:
        modify some invalid value in excel sheet to match database requirement.
        empty accessions ("" or "NA") become "".
        "NA" for date become 1970-01-01.
        "NA" in number fields become -1.
        all float value round to 2 digits.
        """
        value = cell_obj.value
        ctype = cell_obj.ctype
        data_type = self.meta_structure.get_data_type(self.sheet_name, column_header)
        # Now begin validation:
        # ipdb.set_trace()
        if column_header == "User accession" and (value == "NA" or value == ""):  # always us "" if user accession is empty or NA
            value = ""
        elif column_header == "System Accession" and (value == "NA" or value == ""):  # always us "" if sys accession is empty or NA
            value = ""
        elif ctype == CTYPE_BOOLEAN:
            if value:
                value = "TRUE"
            else:
                value = "FALSE"
        # now consider data_type:
        elif data_type == "text" and ctype == CTYPE_NUMBER:
            value = str(value).rstrip('0').rstrip('.')  # delete trailing 0s if it is a number.
        elif data_type == "date":
            if value == "NA" or value == "":
                value = '1970-01-01'
            elif ctype == CTYPE_DATE:
                value = xlrd.xldate.xldate_as_datetime(value, datemode).date().isoformat()
        elif data_type == "number":
            if ctype == CTYPE_NUMBER:
                value = round(value, 2)
            elif value == "NA" or value == "":  # assign number field to -1 if it is NA in the excel.
                value = -1
                logging.info("Change NA to -1 for %s in %s." % (column_header, self.sheet_name))
            else:
                sys.exit("please use number for %s in %s" % (column_header, self.sheet_name))
        elif data_type == "textnumber":
            if ctype == CTYPE_NUMBER:
                value = round(value, 2)

        self.add(column_header, value)  # or use columan display name?
