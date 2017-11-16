import uuid  # used to generate unique user accesion if it is not provided.


class RowData:
    def __init__(self, sheet_name, meta_structure):
        self.sheet_name = sheet_name
        self.meta_structure = meta_structure
        self.schema = dict()
        self.relationships = dict()

    def add(self, column_header, value):
        """Add or replace value in column. Convert "NA" in link columns to "". """
        sheet_name = self.sheet_name
        meta_structure = self.meta_structure
        column_name = meta_structure.get_column_name(sheet_name, column_header)
        if column_header in meta_structure.get_link_column_headers(sheet_name):
            # do link stuff
            if value == "NA":
                value = ""
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
            raise RowError("unknown column %s in %s!" % (column_header, sheet_name))

    def remove(self, column_name):
        """
        It's input is a column_name, instead of a column_header! And it only works for column names in schema. I use it only to delete accession columns.
        """
        if column_name in self.schema:
            return self.schema.pop(column_name)
        else:
            raise RowError("remove method can only delete schema columns, but you are trying to delete %s in %s" % (column_name, self.sheet_name))

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


class RowError:
    """Errors process row data in excel file"""
    pass
