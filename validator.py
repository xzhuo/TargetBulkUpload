class Validator:
    def __init__(self, meta_structure):
        self.meta_structure = meta_structure

    def is_accession_valid(self, sheet_name, row_data):
        user_accession_rule = self.meta_structure.get_user_accession_rule(sheet_name)
        system_accession_rule = self.meta_structure.get_system_accession_rule(sheet_name)

        if "user_accession" not in row_data.schema:
            row_data.schema["user_accession"] = ""
        user_accession = row_data.schema["user_accession"]
        if "accession" not in row_data.schema:
            row_data.schema["accession"] = ""
        system_accession = row_data.schema["accession"]
        valid = False
        if user_accession.startswith(user_accession_rule) and system_accession.startswith(system_accession_rule):
            valid = True
        elif user_accession.startswith(user_accession_rule) and system_accession == "":
            valid = True
        elif user_accession == "" and system_accession.startswith(system_accession_rule):
            valid = True
        return valid