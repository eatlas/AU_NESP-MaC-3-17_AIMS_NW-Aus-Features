from data_downloader import DataDownloader
from pyproj import CRS
import os
import configparser

# Read configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')
download_path = config.get('general', 'in_3p_path')

# Create an instance of the DataDownloader class
downloader = DataDownloader(download_path=download_path)

print("Downloading source data files. This will take a while ...")

# --------------------------------------------------------
#Lawrey, E. P., Stewart M. (2016) Complete Great Barrier Reef (GBR) Reef and Island Feature boundaries including Torres Strait (NESP TWQ 3.13, AIMS, TSRA, GBRMPA) [Dataset]. Australian Institute of Marine Science (AIMS), Torres Strait Regional Authority (TSRA), Great Barrier Reef Marine Park Authority [producer]. eAtlas Repository [distributor]. https://eatlas.org.au/data/uuid/d2396b2c-68d4-4f4b-aab0-52f7bc4a81f5
direct_download_url = 'https://nextcloud.eatlas.org.au/s/xQ8neGxxCbgWGSd/download/TS_AIMS_NESP_Torres_Strait_Features_V1b_with_GBR_Features.zip'
downloader.download_and_unzip(direct_download_url, 'GBR_AIMS_Complete-GBR-feat_V1b')


# --------------------------------------------------------
# Natural Earth. (2025). Natural Earth 1:10m Physical Vectors - Land [Shapefile]. https://www.naturalearthdata.com/downloads/10m-physical-vectors/
#direct_download_url = 'https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip'
#downloader.download_and_unzip(direct_download_url, 'ne_10m_land')



# Beaman, R. (2017). High-resolution depth model for the Great Barrier Reef - 30 m [Dataset]. Geoscience Australia. http://dx.doi.org/10.4225/25/5a207b36022d2
#direct_download_url = 'https://files.ausseabed.gov.au/survey/Great%20Barrier%20Reef%20Bathymetry%202020%2030m.zip'
#downloader.download_and_unzip(direct_download_url, 'CS_GA_GBR30-2020-Bathy')

# --------------------------------------------------------
# Australian Coastline 50K 2024 (NESP MaC 3.17, AIMS)
# https://eatlas.org.au/geonetwork/srv/eng/catalog.search#/metadata/c5438e91-20bf-4253-a006-9e9600981c5f
# Hammerton, M., & Lawrey, E. (2024). Australian Coastline 50K 2024 (NESP MaC 3.17, AIMS) (2nd Ed.) [Data set]. eAtlas. https://doi.org/10.26274/qfy8-hj59
direct_download_url = 'https://nextcloud.eatlas.org.au/s/DcGmpS3F5KZjgAG/download?path=%2FV1-1%2F&files=Split'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Coastline_50k_2024', subfolder_name='Split', flatten_directory=True)

# Use this version for overview maps
direct_download_url = 'https://nextcloud.eatlas.org.au/s/DcGmpS3F5KZjgAG/download?path=%2FV1-1%2F&files=Simp'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Coastline_50k_2024', subfolder_name='Simp', flatten_directory=True)

# --------------------------------------------------------
# Australian Marine Parks
# DCCEEW (2018). Australian Marine Parks (Version 10 Feb 2025) [Dataset]. Department of Agriculture, Water and the Environment. 
# https://fed.dcceew.gov.au/datasets/erin::australian-marine-parks/about
direct_download_url = 'https://hub.arcgis.com/api/v3/datasets/2b3eb1d42b8d4319900cf4777f0a83b9_0/downloads/data?format=shp&spatialRefId=4283&where=1%3D1'
downloader.download_and_unzip(direct_download_url, 'AU_DCCEEW_Australia-Marine-Parks_2025')


# --------------------------------------------------------
# UNEP-WCMC, WorldFish Centre, WRI, TNC (2021). Global distribution of warm-water coral reefs, 
# compiled from multiple sources including the Millennium Coral Reef Mapping Project. Version 4.1. 
# Includes contributions from IMaRS-USF and IRD (2005), IMaRS-USF (2005) and Spalding et al. (2001). 
# Cambridge (UK): UN Environment World Conservation Monitoring Centre. Data DOI: https://doi.org/10.34892/t2wk-5t34
#subfolder_name='14_001_WCMC008_CoralReefs2021_v4_1'
direct_download_url = 'https://datadownload-production.s3.us-east-1.amazonaws.com/WCMC008_CoralReefs2021_v4_1.zip'
downloader.download_and_unzip(direct_download_url, 'World_WCMC_CoralReefs2021_v4_1', flatten_directory=True)

# --------------------------------------------------------
# Lawrey, E., & Hammerton, M. (2022). Coral Sea features satellite imagery and raw depth contours (Sentinel 2 and Landsat 8) 2015 – 2021 (AIMS) [Data set]. eAtlas. https://doi.org/10.26274/NH77-ZW79

# We set the subfolder_name because we are downloading multiple folders into the same parent folder. This allows the script
# to check if the sub part of the dataset has been downloaded already. Without this the TrueColour download is skipped because
# the Coral-Sea-Features_Img folder already exists.
#dataset = 'Coral-Sea-Features_Img'

#layer = 'S2_R1_DeepFalse'
#direct_download_url = f'https://nextcloud.eatlas.org.au/s/NjbyWRxPoBDDzWg/download?path=%2Flossless%2FCoral-Sea&files={layer}'
#downloader.download_and_unzip(direct_download_url, dataset, subfolder_name = layer, flatten_directory = True)
#downloader.create_virtual_raster(dataset, layer=layer)


# ICSM (2018) ICSM ANZLIC Committee on Surveying and Mapping Data Product Specification for Composite Gazetteer of Australia, The Intergovernmental Committee on Surveying and Mapping. Accessed from https://placenames.fsdf.org.au/ on 23 Jan 2025
# https://s3.ap-southeast-2.amazonaws.com/fsdf.placenames/DPS/Composite+Gazetteer+DPS.pdf
#direct_download_url = 'https://d1tuzeg87mu4oi.cloudfront.net/PlaceNames.gpkg'
#downloader.download(direct_download_url, 'AU_ICSM_Gazetteer_2018')

# Lawrey, E. (2025) Semi-automated Shallow Marine Mask for Northern Australia and GBR Derived from Sentinel-2 Imagery (NESP MaC 3.17, AIMS) (Version 1-1) [Data set]. eAtlas. https://doi.org/10.26274/x37r-xk75
direct_download_url = f'https://nextcloud.eatlas.org.au/s/iMrFB9WP9EpLPC2/download?path=%2FV1-1%2Fout%2Flow'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Shallow-mask', flatten_directory = True)

# Lawrey, E. (2025) Semi-automated Shallow Intertidal Rocky Reefs of Northern Australia (NESP MaC 3.17, AIMS) (Version 1)
# https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Rocky-reefs
# https://github.com/eatlas/AU_NESP-MaC-3-17_AIMS_Rocky-reefs
direct_download_url = f'https://nextcloud.eatlas.org.au/s/QD84aRGoKYs3KtP/download?path=%2FV1%2Fout'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Rocky-reefs', flatten_directory = True)



