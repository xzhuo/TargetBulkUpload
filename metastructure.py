import sys
import requests

ACCESSION_PLACEHOLDER_DIGITS = 3
URL_META = 'http://target.wustl.edu:7006'
URL_SUBMIT = 'http://target.wustl.edu:7002'
TESTURL_META = 'http://target.wustl.edu:8006'
TESTURL_SUBMIT = 'http://target.wustl.edu:8002'


class MetaStructure:
    def __init__(self, is_production, all_categories, schema_string='/schema/', relationship_string='/schema/relationships/', version_string='/api/version'):
        """
        Set up metastructure.

        :param: url - it is the meta_url used for submission.
        :param: categories - it is the ALLCATEGORIES dictionary. the key is category, the value is sheet_name.
        :param: schema_string: - it is the the schema string part of the url.
        :param: relationship_string: - it is the relationship string part of the url.
        :param: version_string: it is the version string parl of the url
        :return:

        :attributes: url - the meta_url
        :categories: the category-sheet_name dictionary.
        :version: the version of current system, retrived from a get request.
        :schema_dict: the dictionary with all the schema structure. Each schema_dict[sheet_name] is a list of dictionary.
        An example with experiment, the last item (system accession) is added after the get request.
        {
            "Experiment": [
                {
                    name: "user_accession",
                    text: "User accession",
                    placeholder: "USREXP####",
                    type: "text",
                    required: false
                },
                {
                    name: "experiment_alias",
                    text: "Experiment Alias",
                    placeholder: "",
                    type: "text",
                    required: true
                },
                {
                    name: "design_description",
                    text: "Design Description",
                    placeholder: "",
                    type: "textarea",
                    required: false
                },
                {
                    name: "accession",
                    text: "System Accession",
                    type: "text"
                }
            ]
            ...
        }
        :link_dict: the dictionary with all the linkage structure. Each link_dict[sheet_name] is a dictionary {"one": category, "all": categories, "prefix"}
        An example with experiment:
        {
            "Experiment": {
                one: "experiment",
                all: "experiments",
                prefix: "TRGTEXP000",
                usr_prefix: "USREXP000",
                connections: [
                    {
                        name: "performed_under",
                        placeholder: "Link to Bioproject accession",
                        to: "bioproject",
                        all: "bioprojects",
                        display_name: "Bioproject"
                    }
                ]
            }
            ...
        }
        """
        if is_production:
            self.action_url_meta = URL_META
            self.action_url_submit = URL_SUBMIT
        else:
            self.action_url_meta = TESTURL_META
            self.action_url_submit = TESTURL_SUBMIT
        self.url = self.action_url_meta
        self.category_to_sheet_name = self._set_category_to_sheet_name(all_categories)  # it is a dictionary
        self.schema_dict = self._url_to_json(schema_string)
        self.link_dict = self._url_to_json(relationship_string)
        self.version = self._set_version(version_string)

        # Add system accession to the schema dictionary:
        for category in self.schema_dict:
            self.schema_dict[category].insert(0, {"name": "accession", "text": "System Accession", "type": "text"})

    # def start_metastructure(self, isproduction, all_categories, schema_string, relationship_string, version_string):
    #     # FIXME Move to separate file
    #     if isproduction:
    #         action_url_meta = URL_META
    #         action_url_submit = URL_SUBMIT
    #     else:
    #         action_url_meta = TESTURL_META
    #         action_url_submit = TESTURL_SUBMIT
    #     meta_structure = MetaStructure(action_url_meta, all_categories, schema_string, relationship_string, version_string)
    #     return meta_structure`

    def get_sheet_url(self, sheet_name):
        """Return a url of the provided sheet name."""
        pass

    def get_category(self, sheet_name):
        """
        Return the category name (file) of the provided sheet name (File).

        :param: sheet_name - the excel worksheet name.
        :return: the category name.
        """
        return self.link_dict[sheet_name]["one"]

    def get_categories(self, sheet_name):
        """
        Return the categories (files) of the provided sheet name (File).

        :param: sheet_name - the sheet_name in excel file
        :return: the name of "categories"
        """
        return self.link_dict[sheet_name]["all"]

    def get_sheet_schema(self, sheet_name):
        """Return the sheet schema (a list of dictionary, structure example: http://target.wustl.edu:8006/schema/file.json)."""
        return self.schema_dict[sheet_name]  # schema is a list

    def get_sheet_link(self, sheet_name):
        """Return the sheet link (a dictionary, structure example: http://target.wustl.edu:8006/schema/relationships/file.json)."""
        return self.link_dict[sheet_name]  # link is a dictionary, link["connections"] is a list.

    def get_user_accession_rule(self, sheet_name):
        """
        Return the acceptable user accession rule of metadata database given a sheet name.

        :param: sheet_name - the excel sheet name
        :return: the user accession rule prefix for the sheet.
        """
        link = self.get_sheet_link(sheet_name)
        return link["usr_prefix"][:-ACCESSION_PLACEHOLDER_DIGITS]

        # alternative solution:
        # schema = self.get_schema(sheet_name)
        # return [x["placeholder"] for x in schema if x["text"] == "User accession"][0][:-4]

    def get_system_accession_rule(self, sheet_name):
        """
        Return the acceptable system accession rule of metadata database given a sheet name.

        :param: sheet_name - the excel sheet name
        :return: the system accession rule prefix for the sheet.
        """
        link = self.get_sheet_link(sheet_name)
        return link["prefix"][:-ACCESSION_PLACEHOLDER_DIGITS]

    def get_schema_column_headers(self, sheet_name):  # get a list of all column display names, including "System Accession"
        """Return a list of all column display names except relationship columns. Because of L123-125, "System Accession" is also in the list."""
        schema = self.get_sheet_schema(sheet_name)
        return [x["text"] for x in schema]

    def get_link_column_headers(self, sheet_name):  # get a list of all column display names
        """Return a list of all relationship column display names."""
        link = self.get_sheet_link(sheet_name)
        return [x["display_name"] for x in link["connections"]]

    def get_schema_column_names(self, sheet_name):  # get a list of all column names, including "accession"
        """Return a list of all column names except relationship columns. Because of L123-125, "accession" is also in the list."""
        schema = self.get_sheet_schema(sheet_name)
        return [x["name"] for x in schema]

    def get_link_column_names(self, sheet_name):  # get a list of all column names
        """Return a list of all relationship column names."""
        link = self.get_sheet_link(sheet_name)
        return [x["name"] for x in link["connections"]]

    def get_all_column_headers(self, sheet_name):
        """Return a list of all column display names. Because of L123-125, "System Accession" is also in the list."""
        return self.get_schema_column_headers(sheet_name) + self.get_link_column_headers(sheet_name)

    def get_data_type(self, sheet_name, column_header):
        """
        Given a excel sheet name and a column display name (column header), return the expected data type of that column in the database.

        :param: sheet_name - the sheet name! what the fuck do you expect?!
        :param: column_header - the column header shown in the excel file.
        :return: the data type of that column, for relationship it is always a "text"
        """
        return self._get_column_info(sheet_name, column_header, "type")

    def get_column_name(self, sheet_name, column_header):
        """Get the field name (column_name) in database using column header in excel."""
        return self._get_column_info(sheet_name, column_header, "name")

    def get_linkto(self, sheet_name, column_header):
        """
        Given a excel sheet name and relationship column display name (column_header), returns which sheet that relationship links to.

        :param: sheet_name
        :param: column_header
        :return: another sheet_name the columna_header in sheet_name linked to.
        """
        if column_header in self.get_link_column_headers(sheet_name):
            link = self.get_sheet_link(sheet_name)
            category = [x["to"] for x in link["connections"] if x["display_name"] == column_header][0]
            return self.category_to_sheet_name[category]
        else:
            sys.exit("%s in %s is not a connection column" % (column_header, sheet_name))

    def _url_to_json(self, string):
        """Fetch the data from a url and get a dictionary or a list."""
        new_dict = {}
        for category, sheet_name in self.category_to_sheet_name.items():
            json_url = self.url + string + category + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            new_dict[sheet_name] = data
        return new_dict

    def _set_category_to_sheet_name(self, all_categories):  # it is a dictionary
        return {k: k.lower().title() for k in all_categories}

    def _set_version(self, version_string):
        """ Giver a version string (part of the url), returns the latested database structure version."""
        full_url = self.url + version_string
        return requests.get(full_url).json()

    def _get_column_info(self, sheet_name, column_header, info):
        """
        Given a excel sheet name and a column displayname (column_header), returns desired infomation.

        if info == "name", returns the database field name (column_name).
        if info == "type", returns the column"s data type. if it is a relationship column, returns "text" always.
        info is either "type" or "name"
        """
        if column_header in self.get_schema_column_headers(sheet_name):
            info_list = [x[info] for x in self.get_sheet_schema(sheet_name) if x["text"] == column_header]
            info = info_list[0]
        elif column_header in self.get_link_column_headers(sheet_name):
            if info == "type":
                info = "text"
            else:  # info == "name"
                info_list = [x[info] for x in self.get_sheet_link(sheet_name)["connections"] if x["display_name"] == column_header]
                info = info_list[0]
        else:
            sys.exit("unknow info %s of %s in %s" % (info, column_header, sheet_name))
        return info
