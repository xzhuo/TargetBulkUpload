# populate_metadata_Excel.py
# TaRGET II DCC
# Exports a blank Excel metadata template or populates with previously submitted user metadata (--submission [url])
# Copyright 2017, Erica Pehrsson, erica.pehrsson@wustl.edu
# Incorporating code from JSON2Excel.py, copyright Ananda Datta, ananda.datta@wustl.edu

#Module load python2

import sys
import requests
import xlsxwriter
import json
import argparse
import datetime
import submission_oo

# Got all the constant from submission.py.

meta_structure = MetaStructure(action_url_meta, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)

def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--submission',
        '-s',
        action="store",
        dest="submission",
        required=False,
        help="submission id. If provided, it will fetch the specific submission. Without it it will produce an empty excel template.\n",
    )
    parser.add_argument(
        '--notest',
        '-n',
        action="store_true",
        dest="notest",
        help="test flag. default option is true, which will get records from the test database. \
        The metadata only fetch records from the production database if this option is false.\n",
    )
    return parser.parse_args()

def main():
    args = get_args()

    meta_structure = submission_oo.MetaStructure.start_metastructure(args.notest, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)
    version = meta_structure.version
    if args.submission:
        #Retrieve submission JSON
        submission_string = requests.get(args.submission).text
        submission = json.loads(submission_string)['submission']

        #Create workbook
        if "_id" not in submission:
            sys.exit("failed get request at line 39!")
        workbook = xlsxwriter.Workbook('TaRGET_metadata_sub_'+submission["_id"]+'_V'+version+'.xlsx') #The submission should be extracted, replace url
    else:
        workbook = xlsxwriter.Workbook('TaRGET_metadata_V'+version+'.xlsx')

    #Create Instructions worksheet 
    sheet0 = workbook.add_worksheet('Instructions')
    sheet0.write(0,0,'Version '+version) #This will need to come from URL, not hardcoded
    sheet0.write(1,0,'Updated Aug 29, 2017')
    sheet0.write(2,0,'Note: All fields except System Accession and User Accession are required unless otherwise specified.')
    sheet0.write(3,0,'Note: User Accessions are placeholders used to link entries together prior to submission. They must follow the specified format (e.g, URSBPRxxx) and be unique within this workbook. Once submitted, each entry will be automatically assigned a System Accession (e.g., TRGTBPRxxx). Metadata can be updated by resubmitting entries with the System Accession field populated.')
    sheet0.write(4,0,'Note: Required metadata fields are colored gold, while optional fields are orange. Metadata connections are colored blue. To create a connection, specify the accession (user or system) of the object you wish to link to.')
    sheet0.write(5,0,'Note: Experiments organize data files within the Data Portal. Please group together technical replicates within a single Experiment.')

    #Create Lists worksheet
    sheet1 = workbook.add_worksheet('Lists')
    lists = 0
    for category, sheet_name in meta_structure.categories.items():
        #print category
        sheet_schema = meta_structure.get_sheet_schema(sheet_name)
        sheet_relationships = meta_structure.get_sheet_link(sheet_name)
        sheet = workbook.add_worksheet(sheet_name)

        #Print out standard headers and formatting for each sheet
        bold_format = workbook.add_format({'bold': True})
        sheet.write(0,0,sheet_name,bold_format)
        user_accession_format = meta_structure.get_user_accession_rule(sheet_name) + "####"  # with 4 # at the end of user accession rule here.
        sheet.write(0,1,user_accession_format,bold_format)

        #Column headers
        bold_gray = workbook.add_format({'bold': True,'bg_color': 'B6B6B6'})
        sheet.write(1,0,'System Accession',bold_gray)
        #Field columns
        bold_color3 = workbook.add_format({'bold': True,'bg_color': 'FED254'})  # format3
        bold_color4 = workbook.add_format({'bold': True,'bg_color': 'FFB602'})  # format4
        bold_color5 = wb.add_format({'bold': True,'bg_color': 'B0CDEA'})        # format5

##################### old script ####################
#Metadata categories. Each will be printed to a separate tab.
categories = ['litter','mouse','diet','treatment','biosample','library','assay','reagent','file','mergedFile','experiment']
category_plural = { #Is there a URL to replace these dictionaries?
'lab':'labs',
'bioproject':'bioprojects',
'litter':'litters',
'mouse':'mice',
'diet':'diets',
'treatment':'treatments',
'biosample':'biosamples',
'library':'libraries',
'assay':'assays',
'reagent':'reagents',
'file':'files',
'mergedFile':'mergedFiles',
'experiment':'experiments'
}

parser = argparse.ArgumentParser(description='Print TaRGET metadata Excel template. Use --submission flag to add URL of previous submission. Specify --dev or --prod to select database.')
parser.add_argument("--submission",help="Prints user data to Excel template. Provide URL of submission JSON.") #To print user data to template; otherwise, blank template
env = parser.add_mutually_exclusive_group()
env.add_argument("--dev",action="store_true")
env.add_argument("--prod",action="store_true")
args = parser.parse_args()

environment = 8006 #Database set to dev by default
if args.prod:
    environment = 7006

# Get current version
version = requests.get('http://meta.target.wustl.edu/api/version').json()["current"]

if args.submission:
    #Retrieve submission JSON
    submission_string = requests.get(args.submission).text
    submission = json.loads(submission_string)['submission']
    # ipdb.set_trace()

    # submission = requests.get(args.submission).json() 
    # submission = json.load(open(args.submission,'r')) #Replace with prevous when availalble
    #Create workbook
    if "_id" not in submission:
        sys.exit("failed get request at line 39!")
    wb = xlsxwriter.Workbook('TaRGET_metadata_sub_'+submission["_id"]+'_V'+version+'.xlsx') #The submission should be extracted, replace url
else:
    wb = xlsxwriter.Workbook('TaRGET_metadata_V'+version+'.xlsx')

#Create Instructions worksheet 
sh0 = wb.add_worksheet('Instructions')
sh0.write(0,0,'Version '+version) #This will need to come from URL, not hardcoded
sh0.write(1,0,'Updated Aug 29, 2017')
sh0.write(2,0,'Note: All fields except System Accession and User Accession are required unless otherwise specified.')
sh0.write(3,0,'Note: User Accessions are placeholders used to link entries together prior to submission. They must follow the specified format (e.g, URSBPRxxx) and be unique within this workbook. Once submitted, each entry will be automatically assigned a System Accession (e.g., TRGTBPRxxx). Metadata can be updated by resubmitting entries with the System Accession field populated.')
sh0.write(4,0,'Note: Required metadata fields are colored gold, while optional fields are orange. Metadata connections are colored blue. To create a connection, specify the accession (user or system) of the object you wish to link to.')
sh0.write(5,0,'Note: Experiments organize data files within the Data Portal. Please group together technical replicates within a single Experiment.')

#Create Lists worksheet
sh1 = wb.add_worksheet('Lists')
lists = 0 

#Print out data for each metadata category (one sheet each)
for category in categories:
    #print category
    schema = requests.get('http://target.wustl.edu:'+str(environment)+'/schema/'+category+'.json').json()
    relationships = requests.get('http://target.wustl.edu:'+str(environment)+'/schema/relationships/'+category+'.json').json()
    sh = wb.add_worksheet(category.title())

#Print out standard headers and formatting for each sheet
    format1 = wb.add_format({'bold': True})
    sh.write(0,0,category.title(),format1)
    sh.write(0,1,schema['data'][0]['placeholder'],format1) 

    #Column headers
    format2 = wb.add_format({'bold': True,'bg_color': 'B6B6B6'})
    sh.write(1,0,'System Accession',format2)
    #Field columns
    format3 = wb.add_format({'bold': True,'bg_color': 'FED254'})
    format4 = wb.add_format({'bold': True,'bg_color': 'FFB602'})
    for m in range(0,len(schema['data'])):
        #Write header
        if schema['data'][m]['required'] == False: #Color-coding required and optional fields
            sh.write(1,m+1,schema['data'][m]['text'],format4)    
        else:
            sh.write(1,m+1,schema['data'][m]['text'],format3)
        #Write comment
        if len(schema['data'][m]['placeholder']) > 0:
            sh.write_comment(1,m+1,schema['data'][m]['placeholder'])
        #Format entire column
        if 'values' in schema['data'][m]: #Drop-down
            if schema['data'][m]['values_restricted'] == True: #Drop-down with restricted values
                sh.data_validation(2,m+1,10000,m+1,{'validate': 'list',
                                         'source': schema['data'][m]['values'],
                                         'input_title': 'Enter a value:',
                                         'input_message': 'Select an option.',
                                         'error_title': 'Error:',
                                         'error_message': 'Select value from list.'
                                        }) 
            else: #Drop-down with non-restricted values 
                sh.data_validation(2,m+1,10000,m+1,{'validate':'length', #Work on this
                                         'criteria': '>',
                                         'value': 1,
                                         'input_message': 'Enter value from Lists: '+schema['data'][m]['text']+' (Column '+chr(lists+65)+') OR enter own value.' 
                                        })                            
                sh1.write(0,lists,schema['data'][m]['text'],wb.add_format({'bold': True,'font_color': 'red'}))
                for p in range(0,len(schema['data'][m]['values'])):
                    sh1.write(p+1,lists,schema['data'][m]['values'][p])
                lists += 1
    #Connection columns
    format5 = wb.add_format({'bold': True,'bg_color': 'B0CDEA'})
    for n in range(0,len(relationships['data']['connections'])):
        sh.write(1,n+m+2,relationships['data']['connections'][n]['display_name'],format5)
        if len(relationships['data']['connections'][n]['placeholder']) > 0:
            sh.write_comment(1,n+m+2,relationships['data']['connections'][n]['placeholder'])

#Write each object onto a single row, connection fields last
    if args.submission:
        row = 1 #Skip the header rows
        entries_string = submission["details"]
        whole_data = json.loads(entries_string.replace("'", "\"")) #Gets a list of all accessions created for that object category
        format6 = wb.add_format({'num_format': 'mm/dd/yy'}) #Format for date fields
        if category_plural[category] in whole_data:
            entries = whole_data[category_plural[category]]
            for entry in entries:
                row += 1 #Move to the next row
                temp = requests.get('http://target.wustl.edu:'+str(environment)+'/api/'+category_plural[category]+'/'+entry).json()
                if "mainObj" not in temp:
                    sys.exit("failed get request at line 127!")
                sh.write(row,0,entry) #Write System Accession
                column = 1
                for i in range(0,len(schema['data'])):  
                    field = schema['data'][i]['name']
                    datatype = schema['data'][i]['type']
                    req = schema['data'][i]['required']
                    # if field == 'user_accession': #Do not print User Accession for previously submitted data
                    #     sh.write(row,column,'')
                    if field in temp["mainObj"][category].keys(): #If field present in database, print; otherwise, "NA"
                        if (datatype == "date"): #For dates, convert to date format if possible
                            try:
                                float(temp["mainObj"][category][field])
                                sh.write(row,column,float(temp["mainObj"][category][field]),format6)
                            except ValueError:
                                sh.write(row,column,temp["mainObj"][category][field])
                        else:
                            sh.write(row,column,temp["mainObj"][category][field])
                    elif req == "true": #Print placeholders only if field is required
                        if datatype == "number":
                            sh.write(row,column,-1)
                        else: 
                            sh.write(row,column,'NA')
                    column += 1
                for j in range(0,len(relationships['data']['connections'])):
                    connection = relationships['data']['connections'][j]['name']
                    for key in temp["mainObj"]["added"][connection]:
                        if key == relationships['data']['connections'][j]['to']:
                            links = temp["mainObj"]["added"][connection][key]
                    # if connection == "assay_input":
                    #     display_name = relationships['data']['connections'][j]['display_name']
                    #     import ipdb; ipdb.set_trace()
                    #     if display_name == "Biosample":
                    #         links = temp["mainObj"]["added"][connection]["biosample"]  # Assumes Biosample is the first
                    #     if display_name == "Library":
                    #         links = temp["mainObj"]["added"][connection]["library"]  # Assumes Library is the second
                    # else:
                    #     links = temp["mainObj"]["added"][connection][temp['mainObj']['added'][connection].keys()[0]] #Assumes there is only one key
                    if len(links) == 1:
                        sh.write(row,column,links[0]) 
                    elif len(links) > 1:
                        sh.write(row,column,','.join(links)) #Use comma to separate entries for those with multiple allowed
                    column += 1

wb.close()
