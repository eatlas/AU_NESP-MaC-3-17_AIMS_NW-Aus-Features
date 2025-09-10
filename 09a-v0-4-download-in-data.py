"""
This scrip downloads datasets that are used in the development and analysis of version v0-4 of the dataset.
This script assumes that you have now downloaded the existing previous versions. This downloads the 
third party public data and it downloads each of the versions of NW-Aus-Features used in the analysis.
The v0-4 is derived from v0-3 and so we download that dataset as input to 09-v0-4-class-cross-walk.py

"""
import configparser
from data_downloader import DataDownloader
import os
    

# Read configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')
download_path = config.get('general', 'in_3p_path')

# Create an instance of the DataDownloader class
downloader = DataDownloader(download_path=download_path)


print("Downloading source data files. This will take a while ...")

# --------------------------------------------------------
# Reef features on the Australian continental shelf derived and aggregated from 
# Australian Hydrographic Service's (AHS) seabed area features (sbdare_a) from the 1 degree S57 file series [for NESP D3]
# https://catalogue.aodn.org.au/geonetwork/srv/eng/catalog.search#/metadata/2e53d926-5d97-4997-b192-dc7dec66943d
# This dataset is used to as part of determining which reefs have already been mapped. We use this dataset to
# rule out reefs in the uncharted areas of the AHO marine charts.
direct_download_url = 'https://data.imas.utas.edu.au/attachments/2e53d926-5d97-4997-b192-dc7dec66943d/sbdare_a_reefs-only.zip'
downloader.download_and_unzip(direct_download_url, 'AU_NESP-D3_AHO_Reefs')


# Download v0-4 starting set of files. This is used as the start of the creation of v0-4 and the analysis of v0-4
downloader.download_path = 'data'
direct_download_url = 'https://nextcloud.eatlas.org.au/s/ZbxtYci3A6WYnHc/download?path=%2Fv0-4'
downloader.download_and_unzip(direct_download_url, 'v0-4', flatten_directory=True)






