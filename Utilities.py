import os


class CustomValues:
    # Config file default value, displayed to the user when asked for input
    ftp_password = 'password'
    ftp_user = 'username'


class CustomKeys:
    # Default key that will be used to access that value in the Config file
    ftp_user = 'ftp_username'
    ftp_password = 'ftp_password'


class UtilityMethods:
    @staticmethod
    def create_dir(basepath, path_ext=""):
        """ Creates the the output directory if it doesn't exist """
        if not os.path.exists(os.path.join(basepath, path_ext)):
            os.makedirs(os.path.join(basepath, path_ext))
