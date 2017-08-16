# Change Log
All notable changes to this project will be documented in this file.


## [0.3.1] - 2-17-08-16
### changes committed
* Now it supportes update records using user accession and link records using user accession (with --saveacc flag)
* User accession now does not require a string start with "USR" anymore.

### TODO
* Update readme, flowchat and tutorial with new function.

## [0.3.0] - 2017-07-14
### changes committed
* Rename ```-u``` flag to ```--saveacc``` and ```-s```.
* Change ```-m``` to ```-update```. It is a boolean flag now. ```-m upload``` is replaced by FALSE (without the flag), ```-m update``` is replaced by TRUE (with ```--update``` flag).
* Update readme with new options.

## [0.2.2] - 2017-07-12
### changes committed
* Add options with ```-u``` flag so users can decide whether save user accession or not.
* Update readme with new options.
* Bug fixes.

## [0.2.1] - 2017-07-10
### changes committed
* Add 'upload' and 'update' modes for the script.
* Rename some variables for clarity.
* Prompt user to confirm before post data during --notest mode.
* Post submission details to a separate url.
* Code aesthetic stuff.
* Grammar edits by Erica.

## [0.2.0] - 2017-06-13
### changes committed
* Add 10 seconds timeout to post request, and print a proper warning message after timeout.
* Support both string in format "YYYY-MM-DD" or excel date format.
* Support connect to experiment by providing experiment system accession number.
* Neither user accession nor system accession is required. Random uuid will be assigned to
user accession if it is blank.
* Verify if all the user accession in relationship columns exist in the
excel file.
* Print a warning message if the relationship connection failed to be
established.

## [0.1.3] - 2017-06-09
### changes committed
* No longer support excel template V1;
* No longer require user accession in all records if there is a system
accession;
* Remove requirement for user accession;
* Change "token" to "API key" in help message;
* Change some message wording.

## [0.1.2] - 2017-06-08
### changes committed
* Use DEV database to test bulk upload.
Now upload records to DEV database as default, only write it to PROD
database with the flag “-notest”. User should upload their data to DEV
as a test.  After successfully upload their excel file to DEV database,
user can upload the same file to PROD database with “-notest” flag.
* Change several EXCEL column names from *(units) to *(include units).
* Print out records in json format on screen before upload.
* Support upload json text file to database (for testing purpose).
* Compatible with excel template 2.0.2

## [0.1.1] - 2017-05-11
### changes committed
* Version verification;
* Report error and exit if duplicated user accession numbers found in one excel sheet;
* Report error and exit with failed POST request.
### TODO:
* CSV file support (maybe?)
* Roll back (delete posted records if any error occured posting following records)
* Discontinue support to excel temple V1

## [0.1.0] - 2017-04-21
### First commit
### TODO:
* CSV file support (maybe?)
