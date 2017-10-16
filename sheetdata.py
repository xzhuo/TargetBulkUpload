class SheetData:
    def __init__(self, sheet_name, meta_structure):
        self.name = sheet_name
        self.meta_structure = meta_structure
        self.all_records = []
        # maybe use iterator for records? see:
        # http://anandology.com/python-practice-book/iterators.html
        # eg.
        # http://biopython.org/DIST/docs/api/Bio.Align-pysrc.html#MultipleSeqAlignment

    def add_record(self, row_data):
        self.all_records.append(row_data)

    def new_row(self):
        row_data = RowData(self.name, self.meta_structure)
        return row_data

    def filter_add(self, row_data):
        """
        1. For records without user accession or system accession, assign "" to the field.
        2. Only add the row_data to self if:
            Both user accession and system accession follow the accession rule;
            One of them follows the accession rule, and the other is "".
        """
        sheet_name = self.name
        if validator.is_accession_valid(sheet_name, row_data):
            self.add_record(row_data)
        else:
            logging.warning("record %s %s in %s is not valid and will be skipped!" % (system_accession, user_accession, sheet_name))