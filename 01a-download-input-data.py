from data_downloader import DataDownloader
from pyproj import CRS
import os
import configparser

# Read configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')
in_3p_path = config.get('general', 'in_3p_path')
data_path = config.get('paths', 'data_path')
version = config.get('general', 'version')

# Create an instance of the DataDownloader class
downloader = DataDownloader(download_path=data_path)

print("Downloading source data files. This will take a while ...")

# --------------------------------------------------------
# Download the input and output data for the current version of the dataset. This will all download in-3p-mirror
# which includes the ReefKIM dataset.
direct_download_url = f'https://nextcloud.eatlas.org.au/public.php/dav/files/ZbxtYci3A6WYnHc/{version}?accept=zip'
downloader.download_and_unzip(direct_download_url, version, flatten_directory=True)


downloader.download_path = in_3p_path  # Switch to the in_3p path for downloading third-party datasets
# --------------------------------------------------------
#Lawrey, E. P., Stewart M. (2016) Complete Great Barrier Reef (GBR) Reef and Island Feature boundaries including Torres Strait (NESP TWQ 3.13, AIMS, TSRA, GBRMPA) [Dataset]. Australian Institute of Marine Science (AIMS), Torres Strait Regional Authority (TSRA), Great Barrier Reef Marine Park Authority [producer]. eAtlas Repository [distributor]. https://eatlas.org.au/data/uuid/d2396b2c-68d4-4f4b-aab0-52f7bc4a81f5
# This was needed to determine the potential overlap point between the existing Torres Strait reef mapping
# and the new mapping in the Gulf of Carpentaria.
direct_download_url = 'https://nextcloud.eatlas.org.au/s/xQ8neGxxCbgWGSd/download/TS_AIMS_NESP_Torres_Strait_Features_V1b_with_GBR_Features.zip'
downloader.download_and_unzip(direct_download_url, 'Complete-GBR-feat_V1b')


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
# This is used for clipping out land areas from the manually edited reef boundaries

# old direct_download_url = 'https://nextcloud.eatlas.org.au/s/DcGmpS3F5KZjgAG/download?path=%2FV1-1%2F&files=Split'
direct_download_url = 'https://nextcloud.eatlas.org.au/public.php/dav/files/DcGmpS3F5KZjgAG/V1-1/Split/?accept=zip'

downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Coastline_50k_2024', subfolder_name='Split', flatten_directory=True)

# Use this version for overview maps and faster intermediate processing steps where the finest
# precision is not needed.
# old direct_download_url = 'https://nextcloud.eatlas.org.au/s/DcGmpS3F5KZjgAG/download?path=%2FV1-1%2F&files=Simp'
direct_download_url = 'https://nextcloud.eatlas.org.au/public.php/dav/files/DcGmpS3F5KZjgAG/V1-1/Simp/?accept=zip'
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
# This dataset was used for creating comparative maps for the NESP showcase presentation. It is also used for identifying
# already mapped reefs (see A02-unmapped-reefs.py)
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

# --------------------------------------------------------
# Flukes, E., (2024). Multi-resolution bathymetry composite surface for Australian waters (EEZ).
# Institute for Marine and Antarctic Studies (IMAS). Data accessed from
# https://metadata.imas.utas.edu.au/geonetwork/srv/eng/catalog.search#/metadata/69e9ac91-babe-47ed-8c37-0ef08f29338a
# on 31 July 2025
# These are 22GB and 37 GB files so they will take a while to download.
# It is used for identifying already mapped reefs (see A02-unmapped-reefs.py), however the bulk of the checking
# was done using AusBathyTopo 250 m.
SKIP_BATHY_DOWNLOAD = True  # Set to True to skip downloading the bathymetry files, which are very large and take a long time to download. This is useful for testing and development when you don't need the full dataset.
if not SKIP_BATHY_DOWNLOAD:
    direct_download_url = 'https://data.imas.utas.edu.au/attachments/69e9ac91-babe-47ed-8c37-0ef08f29338a/bathymetry/01_shallow_bathy.tif'
    downloader.download(direct_download_url, os.path.join(downloader.download_path, 'MultiRes-Bathy-EEZ_2024', '01_shallow_bathy.tif'))

    # We need to mesophotic bathymetry for 30-70m depth range as a lot of deeper reefs are in this range.
    direct_download_url = 'https://data.imas.utas.edu.au/attachments/69e9ac91-babe-47ed-8c37-0ef08f29338a/bathymetry/02_mesophotic_bathy.tif'
    downloader.download(direct_download_url, os.path.join(downloader.download_path, 'MultiRes-Bathy-EEZ_2024', '02_mesophotic_bathy.tif'))

# --------------------------------------------------------
# Geoscience Australia. (2024).AusBathyTopo (Australia) 250m 2024 - A national-scale depth model (20240011C).
# https://doi.org/10.26186/150050
# This is used to identify already mapped reefs in areas outside the coverage of the MultiRes-Bathy-EEZ dataset (see A02-unmapped-reefs.py)
direct_download_url = 'https://files.ausseabed.gov.au/survey/AusBathyTopo%20(Australia)%202024%20250m.zip'
downloader.download_and_unzip(direct_download_url, 'AusBathyTopo-250m_2024')

# --------------------------------------------------------
# GEODATA TOPO 250K Series 3 (Shape file format)
# Geoscience Australia, (2006) GEODATA TOPO 250K Series 3 (Shape file format). Geoscience Australia, Canberra.
# https://pid.geoscience.gov.au/dataset/ga/64058
# The marine hazards layer of this dataset is used to identify already mapped reefs. Used by A02-unmapped-reefs.py
direct_download_url = 'https://d28rz98at9flks.cloudfront.net/64058/64058.zip'
downloader.download_and_unzip(direct_download_url, 'GA_GeoTopo250k_S3')

# --------------------------------------------------------
# ICSM (2018) ICSM ANZLIC Committee on Surveying and Mapping Data Product Specification for Composite Gazetteer of Australia, The Intergovernmental Committee on Surveying and Mapping. Accessed from https://placenames.fsdf.org.au/ on 23 Jan 2025
# https://s3.ap-southeast-2.amazonaws.com/fsdf.placenames/DPS/Composite+Gazetteer+DPS.pdf
#direct_download_url = 'https://d1tuzeg87mu4oi.cloudfront.net/PlaceNames.gpkg'
#downloader.download(direct_download_url, 'AU_ICSM_Gazetteer_2018')

# --------------------------------------------------------
# Lawrey, E. (2025) Semi-automated Shallow Marine Mask for Northern Australia and GBR Derived from Sentinel-2 Imagery (NESP MaC 3.17, AIMS) (Version 1-1) [Data set]. eAtlas. https://doi.org/10.26274/x37r-xk75
# This is used for creating the v0-3 shallow sediment mask used for the UQ habitat mapping
direct_download_url = f'https://nextcloud.eatlas.org.au/s/iMrFB9WP9EpLPC2/download?path=%2FV1-1%2Fout%2Flow'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Shallow-mask', flatten_directory = True)

# --------------------------------------------------------
# Lawrey, E. (2025) Semi-automated Shallow Intertidal Rocky Reefs of Northern Australia (NESP MaC 3.17, AIMS) (Version 1)
# https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Rocky-reefs
# https://github.com/eatlas/AU_NESP-MaC-3-17_AIMS_Rocky-reefs
# This is used for creating the v0-3 shallow sediment mask used for the UQ habitat mapping
direct_download_url = f'https://nextcloud.eatlas.org.au/s/QD84aRGoKYs3KtP/download?path=%2FV1%2Fout'
downloader.download_and_unzip(direct_download_url, 'AU_AIMS_Rocky-reefs', flatten_directory = True)

# --------------------------------------------------------
# Alcock, M.B.,Taffs, N.J., Zhong, Q. (2020) Seas and Submerged Lands Act 1973 - Australian Maritime Boundaries 2020 - Geodatabase. Geoscience Australia. https://pid.geoscience.gov.au/dataset/ga/144571
# This was used to produce maps showing which reefs on the north west shelf are in Australian waters.
direct_download_url = 'https://d28rz98at9flks.cloudfront.net/144571/144571_01_0.zip'
downloader.download_and_unzip(direct_download_url, 'AU_GA_AMB2020', flatten_directory = True)

# --------------------------------------------------------
# Institute for Marine and Antarctic Studies. (2017). Seabed area on the Australian continental shelf and Lord Howe
# Island shelf derived and aggregated from Australian Hydrographic Service’s (AHS) seabed area features (sbdare_a)
# from the 1 degree S57 file series [for NESP D3] [Dataset]. University of Tasmania.
# https://metadata.imas.utas.edu.au/geonetwork/srv/eng/catalog.search#/metadata/f56d4f73-7444-4335-8c46-dce34db915f9
# This dataset is used as part of determining which reefs have already been mapped. We use this dataset to
# rule out reefs in the uncharted areas of the AHO marine charts.
direct_download_url = 'https://data.imas.utas.edu.au/attachments/f56d4f73-7444-4335-8c46-dce34db915f9/sbdare_a.zip'
downloader.download_and_unzip(direct_download_url, 'AU_NESP-D3_AHS_Reefs', flatten_directory = True)

# --------------------------------------------------------
# Natural Earth. (2025). Natural Earth 1:50m Physical Vectors - Land [Shapefile]. https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-land/
downloader.download_and_unzip(
    'https://naciscdn.org/naturalearth/50m/physical/ne_50m_land.zip',
    'natural-earth-land-50m',
    flatten_directory=True
)

# --------------------------------------------------------
# Natural Earth. (2025). Natural Earth 1:50m Admin 0 – Countries [Shapefile]. https://www.naturalearthdata.com/downloads/50m-cultural-vectors/
# https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/50m/cultural/ne_50m_admin_0_countries.zip
# This dataset is used for creating base land maps, particularly for neighbouring countries other than Australia.
downloader.download_and_unzip(
    'https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip',
    'natural-earth-admin-0-countries-50m',
    flatten_directory=True
)

# --------------------------------------------------------
# Department of Climate Change, Energy, the Environment and Water. (2025). 
# Collaborative Australian Protected Areas Database (CAPAD) 2024 - Marine. [Data set].
# https://fed.dcceew.gov.au/datasets/erin::collaborative-australian-protected-areas-database-capad-2024-marine/about
# This dataset is available under the CC-BY data licencing model and users are required to acknowledge 
# the Australian Government, Department of Climate Change, Energy, the Environment and Water as the source 
# of the data in any of their uses. When citing the data please use 'Collaborative Australian Protected 
# Areas Database (CAPAD) 2024, Commonwealth of Australia 2025'.
# This dataset is used in A02-unmapped-reefs to determine what fraction of reefs is within protected areas.
# We need to keep the directory name very short due to the long file names in the CAPAD dataset.
downloader.download_and_unzip(
    'https://hub.arcgis.com/api/v3/datasets/0b6e7b6c48a64a3a82c225fa48aee13d_1/downloads/data?format=shp&spatialRefId=4283&where=1%3D1',
    'CAPAD-2024',
    flatten_directory=True
)





