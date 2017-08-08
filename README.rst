TargetBulkUpload
================

Bulk upload of metadata to TaRGET II DCC

Install python3
---------------

Prepare library (if necessary)
------------------------------

::

    pip3 install xlrd

Description
-----------

This script can be used to upload metadata to the TaRGET II DCC metadata
database from a specific Excel template. You can use it to: 1. Upload
new metedata to the database; 2. Update existing records in the
database; 3. Establish relationships between metadata records.

How to use it
-------------

Download the script alone with latest excel template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ::

       git clone https://github.com/xzhuo/TargetBulkUpload.git

2. Or You can click the "clone or download" button.

Obtain your personal API key
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Visit http://target.wustl.edu:8002/login.
-  Log in with your user name and password.
-  Click "Show API key".
-  Copy your API key string.

Decide what do you want to do with the "user accession" column in the excel file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

| Before fill in the excel template, you must decide how do you want to
  use the "user accession" column.
| User accession can be used as a temporary accession to link different
  records and establish relationships. In this case, the user accessions
  you entered in the excel will be removed once your records get their
  system accessions.

The user accession can also have actural meaning to you and you want to
save your user accession in our database. In this case, records
submitted by a same user must have unique user accession. please make
sure all your records have unique user accessions.

Summary: \* Don't use the ``--saveacc`` flag if: \* Your user accession
in the excel file is temporary; \* You only use user accession to link
records in the excel file; \* You may have some row without a user
accession; \* You can make sure every row in the excel file is a new
record you need to submit to your database.

-  Always use the ``--saveacc`` flag if:

   -  You need to save user accession information in our database;
   -  all your records you have submitted, you are submitting, and you
      are going to submit must have unique user accessions. (all your
      records in different batches must have unique user accessions!)

If you want to upload new data to the metadata database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Fill in the Excel template accordingly. You must use the template in
   the repo. Don't rename the template; if you have to rename it, keep
   the version number intact in the name.

   -  Leave the "System Accession" column blank for the records you want
      to upload. If a system accession is found in a row, the data in
      the row will not be uploaded. However, both the "system accession"
      and the "user accession" in that row now point to the same record
      in the metadata database, and either one can be used to establish
      linkage.

      -  For example, if you have a mouse record in the excel with a
         system accession "TRGTMSE0001" and a user accession
         "USRMSE0001", the mouse record itself will not be uploaded.
         However, If you want to submit a biosample extracted from the
         mouse, either "TRGTMSE0001" or "USRMSE0001" works if you want
         to link that biosample record to this mouse.

   -  "User Accession" can be used to establish relationships with other
      records in the same Excel file. Please fill in "User Accession"
      according to our accession rules (see "Instructions" tab and
      individual tab headers).
   -  If you don't use the ``--saveacc`` flag, you can leave "user
      accession" blank if you don't need to establish any relationship
      to that record. You can also use "user accession" to link records.
      But make sure all user accessions must be unique in the excel file
      and all your rows are new records to the database.
   -  If you use the ``--saveacc`` flag, you must assign a unique "user
      accession" to all your records.
   -  All the dates in the Excel can be a date type in Excel format or a
      string in format "YYYY-MM-DD". Don't worry if Excel changes the
      date format automatically (it means Excel knows it is a date).
   -  The relationship columns are labeled with a different color on the
      right side in each sheet. It should be either a "User Accession"
      in the same Excel file or an existing "System Accession" in the
      database.

2. Run it with following command in test mode:

   ::

       python3 submission.py -k <API key> -x <excel file>

   If you are using the ``--saveacc`` flag:

   ::

       python3 submission.py -k <API key> -x <excel file> --saveacc

3. If there is no error during the test run, you can upload the same
   Excel file to the production database with the following command
   (please don't use the following command and contact us if there is
   any unexpected warning or error):

   ::

       python3 submission.py -k <API key> -x <excel file> --notest

   If you are using the ``--saveacc`` flag:

   ::

       python3 submission.py -k <API key> -x <excel file> --saveacc --notest

   .. rubric:: If you want to update existing records in the metadata
      database
      :name: if-you-want-to-update-existing-records-in-the-metadata-database

4. Fill in the Excel template accordingly. You must use the template in
   the repo. Don't rename the template; if you have to rename it, keep
   the version number intact in the name.

   -  To update data in the database, fill in all the applicable columns
      along with the "System Accession" generated by the database.
   -  All the dates in the Excel can be a date type in Excel format or a
      string in format "YYYY-MM-DD". Don't worry if Excel changes the
      date format automatically (it means Excel knows it is a date).
   -  "user accession" column will be ignored duing update.
   -  The relationship columns are labeled with a different color on the
      right side in each sheet. During update, only other record's
      "System Accession" should be used to establish relationships.

5. Run it with following command in test mode (``--saveacc`` flag does
   not affect update):

   ::

       python3 submission.py -k <API key> -x <excel file> --update

6. If there is no error during the test run, you can update the same
   Excel file to the production database with the following command
   (please don't use the following command and contact us if there is
   any unexpected warning or error):

   ::

       python3 submission.py -k <API key> -x <excel file> --update --notest

   .. rubric:: A summary flow chart
      :name: a-summary-flow-chart

   .. figure:: https://github.com/xzhuo/TargetBulkUpload/blob/master/bulkupload_flow.20170714.png
      :alt: submit summary flow chart

      Flow chart
