import rowdata


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
        row_data = rowdata.RowData(self.name, self.meta_structure)
        return row_data
