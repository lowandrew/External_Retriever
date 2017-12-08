# External_Retriever

Given a list of seqids, puts the files specified into a folder and uploads them to the FTP for other labs to use.

To run:

- Go to where you want to download this automator
- `git clone this_repository`
- `cd this_repository`
- `source /mnt/nas/Virtual_Environments/Generic_Redmine/bin/activate`
- `python ExternalRetriever_Run.py`
- You'll be asked for a bunch of parameters. You should be safe hitting enter and leaving them at defaults.
- When asked for your api key, enter it. (Found on redmine under 'My Account')
