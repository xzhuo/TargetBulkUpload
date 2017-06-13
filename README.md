# TargetBulkUpload
Bulk upload data to target dcc

## Install python3

## Prepare library (if necessary)
```
pip3 install xlrd
```

## What is this
The script can be used to upload metadata to TARGET dcc metadata databse from a specific excel template. 
You can use it to:
1. Upload new metedata to the database;
2. Update existing record in the database;
3. Establish relationships between metadata records.

## How to use it
1. Obtain your personal API key.
	* visit http://target.wustl.edu:8002/login.
	* Log in with your user name and password.
	* Click "Show API key"
	* copy your API key string
2. Fill in the excel template accordingly.
	* To upload new data, leave "system accession" column blank.
	* "User accession" can be used to establish relationships with other records in the same excel files. If you need to establish relationships between records, please fill in "user accession" according to our accession rule (you can find the rule at the head of each excel sheet).
	* "User accession" must be unique within a excel file. But you can use the same "user accession" again in another excel file in another batch of upload.
	* You can leave "user accession" blank if you don't need to establish relationship for that record.
	* To update data in the database, fill in all the columns appliable along with the "system accession" in the database.
	* To update existing data, you can assign a unique "user accession" or leave "user accession" column blank.
	* If both "systerm accession" and "user accession" are used, both of them can be used to establish relationship.
	* All the date in the excel can be a date type in excel format, or a string in format "YYYY-MM-DD". Don't worry if excel changed date format automatically, it means excel knows it is a date.
	* The relationship columns are labeled with a different color on the right side in each sheet. It should be either a "user accession" in the same excel file or an existing "system accession" in the database.
3. Run it with following command in test mode:
```
python3 submission.py -k <API key> -x <excel file>
```
4. If there is no error during test run, you can upload same excel file to the production database with the following command (please don't use the following command and contact us if there is any unexpected warning or error):
```
python3 submission.py -k <API key> -x <excel file> --notest
```
