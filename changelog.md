# Change Log
All notable changes to this project will be documented in this file.


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
