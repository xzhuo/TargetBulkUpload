import metastructure
class BookData:
    def __init__(self, meta_structure):
        self.meta_structure = meta_structure
        self.data = dict()
        self.submission_log = dict()

    def add_sheet(self, sheet_data):
        sheet_name = sheet_data.name
        self.data[sheet_name] = sheet_data

    def save_submission(self, sheet_name, accession):
        category = self.meta_structure.get_category(sheet_name)
        if category in self.submission_log:
            self.submission_log[category].append(accession)
        else:
            self.submission_log.update({category: [accession]})

    def swipe_accession(self):
        """
        for all the relationships in the bookdata, point it to a system accession according to user accession.
        """
        accession_table = dict()
        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
            for record in all_records:
                user_accession = record.schema["user_accession"]
                system_accession = record.schema["accession"]
                accession_table.update({user_accession: system_accession})
                old_accession = record.old_accession()
                if old_accession != "":
                    accession_table.update({old_accession: system_accession})

        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
            for record in all_records:
                for column_name in record.relationships:
                    for linkto in record.relationships[column_name]:
                        accession_list = record.relationships[column_name][linkto]
                        for index, accession in enumerate(accession_list):
                            if accession in accession_table:
                                accession_list[index] = accession_table[accession]

#FIXME Put all validation in class SheetValidator or whatever you want to call it
