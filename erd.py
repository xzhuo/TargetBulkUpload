import metastructure
import argparse
import logging


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--is_production',
        '-p',
        action="store_true",
        dest="is_production",
        default="is_production",
        help="test flag. default option is true, which will get records from the test database. \
        The metadata only fetch records from the production database if this option is TRUE.\n",
    )
    return parser.parse_args()


def main():
    color_dict = {"Lab": "#FEE59D",
                  "File": "#FEE59D",
                  "Diet": "#F2B187",
                  "Library": "#F2B187",
                  "Treatment": "#C6DFB6",
                  "Assay": "#C6DFB6",
                  "Litter": "#C6DFB6",
                  "Mouse": "#BED7ED",
                  "Reagent": "#BED7ED",
                  "Experiment": "#BED7ED",
                  "Bioproject": "#D9D9D9",
                  "Biosample": "#D9D9D9",
                  "Mergedfile": "#D9D9D9",
                  }
    args = get_args()
    logging.getLogger().setLevel(logging.INFO)
    is_production = args.is_production
    try:
        meta_structure = metastructure.MetaStructure(is_production)
    except metastructure.StructureError as structure_error:
        logging.error(structure_error)

    print("title {label: \"TaRGET metadata diagram\", size: \"20\"}\n\n# Entities\n")
    for sheet_name in meta_structure.schema_dict.keys():
        # print category
        print("[%s] {bgcolor: \"%s\"}" % (sheet_name, color_dict[sheet_name]))
        sheet_schema = meta_structure.get_sheet_schema(sheet_name)
        for m in range(0, len(sheet_schema)):
            name = sheet_schema[m]['name']
            display_name = sheet_schema[m]['text']
            if not (name == "accession" or name == "user_accession"):
                print("  %s {label: \"%s\"}" % (name, display_name))
    print("\n# Relationships\n")
    for sheet_name in meta_structure.schema_dict.keys():
        sheet_relationships = meta_structure.get_sheet_link(sheet_name)
        for n in range(0, len(sheet_relationships['connections'])):
            link_dict = sheet_relationships['connections'][n]
            if 'allow_multiple' in link_dict and link_dict['allow_multiple']:
                to_symbol = "*"
            else:
                to_symbol = "?"
            # We don't have required info for relationships yet, so the symbol will be either * or +
            connect_to = meta_structure.category_to_sheet_name[link_dict['to']]
            print("%-12s*--%s %s {label: \"%s\"}" % (sheet_name, to_symbol, connect_to, link_dict['name']))


if __name__ == "__main__":
    main()
