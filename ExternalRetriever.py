from RedmineAPI.Utilities import FileExtension, create_time_log
from RedmineAPI.Access import RedmineAccess
from RedmineAPI.Configuration import Setup
import os
import shutil
import glob
import ftplib

from Utilities import CustomKeys, CustomValues


class Automate(object):

    def __init__(self, force):

        # create a log, can be written to as the process continues
        self.timelog = create_time_log(FileExtension.runner_log)

        # Key: used to index the value to the config file for setup
        # Value: 3 Item Tuple ("default value", ask user" - i.e. True/False, "type of value" - i.e. str, int....)
        # A value of None is the default for all parts except for "Ask" which is True
        custom_terms = {CustomKeys.ftp_user: (CustomValues.ftp_user, True, str),
                        CustomKeys.ftp_password: (CustomValues.ftp_password, True, str)}  # *** can be more than 1 ***

        # Create a RedmineAPI setup object to create/read/write to the config file and get default arguments
        setup = Setup(time_log=self.timelog, custom_terms=custom_terms)
        setup.set_api_key(force)

        # Custom terms saved to the config after getting user input
        self.custom_values = setup.get_custom_term_values()
        self.ftp_username = self.custom_values[CustomKeys.ftp_user]
        self.ftp_password = self.custom_values[CustomKeys.ftp_password]
        # *** can be multiple custom values variable, just use the key from above to reference the inputted value ***
        # self.your_custom_value_name = self.custom_values[CustomKeys.key_name]

        # Default terms saved to the config after getting user input
        self.seconds_between_checks = setup.seconds_between_check
        self.nas_mnt = setup.nas_mnt
        self.redmine_api_key = setup.api_key

        # Initialize Redmine wrapper
        self.access_redmine = RedmineAccess(self.timelog, self.redmine_api_key)

        self.botmsg = '\n\n_I am a bot. This action was performed automatically._'  # sets bot message
        # Subject name and Status to be searched on Redmine
        self.issue_title = 'external retrieve'  # must be a lower case string to validate properly
        self.issue_status = 'New'

    def timed_retrieve(self):
        """
        Continuously search Redmine in intervals for the inputted period of time, 
        Log errors to the log file as they occur
        """
        import time
        while True:
            # Get issues matching the issue status and subject
            found_issues = self.access_redmine.retrieve_issues(self.issue_status, self.issue_title)
            # Respond to the issues in the list 1 at a time
            while len(found_issues) > 0:
                self.respond_to_issue(found_issues.pop(len(found_issues) - 1))
            self.timelog.time_print("Waiting for the next check.")
            time.sleep(self.seconds_between_checks)

    def check_fastas_present(self, fasta_list, biorequest_dir):
        missing_fastas = list()
        for seqid in fasta_list:
            if len(glob.glob(os.path.join(biorequest_dir, seqid + '*.fasta'))) == 0:
                missing_fastas.append(seqid)
        return missing_fastas

    def check_fastqs_present(self, fastq_list, biorequest_dir):
        missing_fastqs = list()
        for seqid in fastq_list:
            if len(glob.glob(os.path.join(biorequest_dir, seqid + '*.fastq.gz'))) < 2:
                missing_fastqs.append(seqid)
        return missing_fastqs

    def respond_to_issue(self, issue):
        """
        Run the desired automation process on the inputted issue, if there is an error update the author
        :param issue: Specified Redmine issue information
        """
        self.timelog.time_print("Found a request to run. Subject: %s. ID: %s" % (issue.subject, str(issue.id)))
        self.timelog.time_print("Adding to the list of responded to requests.")
        self.access_redmine.log_new_issue(issue)

        try:
            issue.redmine_msg = "Beginning the process for: %s" % issue.subject
            self.access_redmine.update_status_inprogress(issue, self.botmsg)
            issue.redmine_msg = ''
            ##########################################################################################
            # Step before 1: Make a biorequest folder for this issue.
            biorequest_dir = os.path.join('/mnt/nas/bio_requests/', str(issue.id))
            if not os.path.isdir(biorequest_dir):
                os.makedirs(biorequest_dir)
            # Step 1: Parse description to get lists of FASTA/FASTQ files we want.
            fasta_list = list()
            fastq_list = list()
            description = issue.description.split('\n')
            fasta = False
            fastq = True
            for item in description:
                item = item.upper()
                item = item.rstrip()
                if 'FASTA' in item:
                    fasta = True
                    fastq = False
                    continue
                if 'FASTQ' in item:
                    fastq = True
                    fasta = False
                    continue
                if fasta:
                    fasta_list.append(item)
                elif fastq:
                    fastq_list.append(item)

            # Step 2: Extract files to biorequest dir.
            if len(fasta_list) > 0:
                f = open('seqid.txt', 'w')
                for fasta in fasta_list:
                    f.write(fasta + '\n')
                f.close()
                cmd = 'python2 /mnt/nas/WGSspades/file_extractor.py seqid.txt {} /mnt/nas/'.format(biorequest_dir)
                os.system(cmd)
            if len(fastq_list) > 0:
                f = open('seqid.txt', 'w')
                for fastq in fastq_list:
                    f.write(fastq + '\n')
                f.close()
                current_dir = os.getcwd()
                os.chdir('/mnt/nas/MiSeq_Backup')
                cmd = 'python2 file_extractor.py {current_dir}/seqid.txt {output_folder}'.format(output_folder=biorequest_dir,
                                                                                                 current_dir=current_dir)
                os.system(cmd)
                os.chdir(current_dir)
            # Step 2.5: Notify user if any of the FASTAs/FASTQs they requested weren't found
            missing_fastas = self.check_fastas_present(fasta_list, biorequest_dir)
            missing_fastqs = self.check_fastqs_present(fastq_list, biorequest_dir)
            if len(missing_fastas) > 0:
                self.access_redmine.update_issue_to_author(issue, '\nERROR: Could not find the FASTA files for the '
                                                                  'following SEQIDs on the OLC NAS: {}\n\nPlease check'
                                                                  ' the SEQIDs for the samples you want, create a new'
                                                                  ' issue, and try again.'.format(str(missing_fastas)))
            if len(missing_fastqs) > 0:
                self.access_redmine.update_issue_to_author(issue, '\nERROR: Could not find the FASTQ files for the '
                                                                  'following SEQIDs on the OLC NAS: {}\n\nPlease check'
                                                                  ' the SEQIDs for the samples you want, create a new'
                                                                  ' issue, and try again.'.format(str(missing_fastqs)))
            # Step 3: Zip the biorequest folder, save it as issue_id.zip
            # Step 3: Zip the biorequest folder, save it as issue_id.zip
            shutil.make_archive(root_dir=biorequest_dir,
                                format='zip',
                                base_name=str(issue.id))
            # Step 4: Upload folder to FTP.
            s = ftplib.FTP('ftp.agr.gc.ca', user=self.ftp_username, passwd=self.ftp_password)
            s.cwd('outgoing/cfia-ak')
            f = open(str(issue.id) + '.zip', 'rb')
            s.storbinary('STOR {}.zip'.format(str(issue.id)), f)
            f.close()
            s.quit()
            # Step 5: Cleanup, so we don't take up storage space that we don't have to take up.
            shutil.rmtree(biorequest_dir)
            os.remove(str(issue.id) + '.zip')
            ##########################################################################################
            self.completed_response(issue)

        except Exception as e:
            import traceback
            self.timelog.time_print("[Warning] The automation process had a problem, continuing redmine api anyways.")
            self.timelog.time_print("[Automation Error Dump]\n" + traceback.format_exc())
            # Send response
            issue.redmine_msg = "There was a problem with your request. Please create a new issue on" \
                                " Redmine to re-run it.\n%s" % traceback.format_exc()
            # Set it to feedback and assign it back to the author
            self.access_redmine.update_issue_to_author(issue, self.botmsg)

    def completed_response(self, issue):
        """
        Update the issue back to the author once the process has finished
        :param issue: Specified Redmine issue the process has been completed on
        """
        # Assign the issue back to the Author
        self.timelog.time_print("Assigning the issue: %s back to the author." % str(issue.id))

        issue.redmine_msg = "Files saved on FTP at outgoing/cfia-ak/{}.zip".format(str(issue.id))
        # Update author on Redmine
        self.access_redmine.update_issue_to_author(issue, self.botmsg)

        # Log the completion of the issue including the message sent to the author
        self.timelog.time_print("\nMessage to author - %s\n" % issue.redmine_msg)
        self.timelog.time_print("Completed Response to issue %s." % str(issue.id))
        self.timelog.time_print("The next request will be processed once available")
