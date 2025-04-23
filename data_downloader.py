import urllib.request
import os
import sys
import time
import zipfile
import tempfile
import shutil
import glob
from typing import List
from urllib.parse import urlparse
from osgeo import gdal

gdal.UseExceptions()  # Enables exceptions and silences the warning

class DataDownloader:
    """
    Prompt Primer: 
    The DataDownloader class provides methods for:
      1. Downloading files from a URL with a progress indicator.
      2. Unzipping downloaded files with optional directory checks and flattening.
      3. Moving/copying only a subset of files from a larger download.
    
    DataDownloader(download_path: str = "data-cache")
    - Creates a downloader object, storing downloaded data in `download_path`.

    download(url: str, path: str) -> None
    - Downloads a file from `url` to local `path` (skips if `path` exists).

    unzip(zip_file_path: str, unzip_path: str, path_test: str) -> None
    - Unzips `zip_file_path` into `unzip_path`, skipping if `path_test` subfolder already exists.

    download_and_unzip(url: str, dataset_name: str, subfolder_name: str = None, flatten_directory: bool = False) -> None
    - Downloads a ZIP from `url` and unpacks into `download_path/dataset_name[/subfolder_name]`.
    - If `flatten_directory` is True, moves nested files up one level.

    move_files(patterns: List[str], source_directory: str, destination_directory: str) -> None
    - Moves files from `source_directory` to `destination_directory`, matching each pattern in `patterns`.

    download_unzip_keep_subset(url: str, zip_file_patterns: List[str], dataset_name: str) -> None
    - Downloads a ZIP from `url`, unzips to a temp location, then moves only matching files to `download_path/dataset_name`.

    Class Attributes:
        start_time (float): Tracks the start time of the most recent download.
        last_report_time (float): Tracks the time of the last status update during a download.
        download_path (str): Local base directory for downloaded content.
        tmp_path (tempfile.TemporaryDirectory): Temporary directory object for intermediate operations.
    """

    def __init__(self, download_path: str = "data-cache") -> None:
        """
        Initializes the DataDownloader with an optional download path.

        :param download_path: Base directory where downloaded files are stored.
        """
        self.start_time = 0.0
        self.last_report_time = 0.0
        self.download_path = download_path
        self.tmp_path = tempfile.TemporaryDirectory()  # Holds temporary files during processing

    def _reporthook(self, count: int, block_size: int, total_size: int) -> None:
        """
        A hook function used by urllib.request.urlretrieve to display download progress.

        :param count: The current block count.
        :param block_size: The size of each block in bytes.
        :param total_size: The total size of the file in bytes (or -1 if unknown).
        """
        current_time = time.time()
        if count == 0:
            self.start_time = current_time
            self.last_report_time = current_time
            return
        time_since_last_report = current_time - self.last_report_time
        if time_since_last_report > 1:  # Update progress every 1 second
            self.last_report_time = current_time
            duration = current_time - self.start_time
            progress_size = int(count * block_size)
            speed = int(progress_size / (1024 * duration))

            if total_size != -1:
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write("%d%%, %d MB, %d KB/s, %d secs    \r" %
                                 (percent, progress_size / (1024 * 1024), speed, duration))
            else:
                sys.stdout.write("%d MB, %d KB/s, %d secs    \r" %
                                 (progress_size / (1024 * 1024), speed, duration))
            sys.stdout.flush()

    def _download(self, url: str, path: str) -> None:
        """
        Downloads a file from the given URL to the specified local path.

        If the target file already exists at the destination path, the function will skip the download.
        Otherwise, it downloads the file to a temporary location and then moves it to the desired path.
        During the download, a progress indicator is displayed via the `_reporthook` method.

        :param url: The URL of the file to be downloaded.
        :param path: The local path (including filename) where the file should be saved.
        """
        if os.path.exists(path):
            print(f"Skipping download of {path}; it already exists")
        else:
            print(f"Downloading from {url}")
            dest_dir = os.path.dirname(path)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            tmp_path = path + '.tmp'

            # Define a set of headers to mimic a common browser request. This allows us
            # to download files from websites that may perform user agent checks or reject
            headers = {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/58.0.3029.110 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req) as response, open(tmp_path, 'wb') as out_file:
                total_size = response.getheader('Content-Length')
                total_size = int(total_size) if total_size is not None else -1
                block_size = 32768  # 32 KB block size
                count = 0
                self.start_time = time.time()
                self.last_report_time = time.time()
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    count += 1
                    self._reporthook(count, block_size, total_size)
            os.rename(tmp_path, path)
            print("\nDownload complete")


    def unzip(self, zip_file_path: str, unzip_path: str, path_test: str) -> None:
        """
        Extracts the contents of a specified ZIP file to a designated directory.

        If the directory doesn't exist, it will be created. The function will skip 
        the extraction process if a specified sub-directory (given by `path_test`) 
        already exists within the target extraction directory, suggesting that the 
        unzip operation has likely already been performed.

        :param zip_file_path: Path to the ZIP file to be extracted.
        :param unzip_path: Path to the directory where the ZIP contents should be extracted.
        :param path_test: Sub-directory name (relative to unzip_path) to check as an 
                          indicator if the unzip operation has previously occurred.
        """
        # Normalize unzip_path to ensure no trailing slash
        unzip_path = os.path.normpath(unzip_path)
        unpack_dir = os.path.join(unzip_path, path_test)
        if os.path.exists(unpack_dir):
            print(f"Skipping unzip of {zip_file_path} as unzip path exists: {unpack_dir}")
        else:
            print(f"Unzipping {zip_file_path} to {unzip_path}")
            # Unzip to a temp directory that we rename at the end
            tmp_unzip_path = f'{unzip_path}_tmp'
            os.makedirs(tmp_unzip_path, exist_ok=True)
            absolute_unzip_path = os.path.abspath(tmp_unzip_path)

            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    full_path = os.path.join(absolute_unzip_path, member)
                    if len(full_path) > 260:
                        msg = (f"Extraction path too long for Windows (Max: 260 chars). "
                               f"It is {len(full_path)} characters. {full_path}")
                        raise ValueError(msg)
                zip_ref.extractall(tmp_unzip_path)

            # Rename the tmp_unzip_path to the final name
            os.rename(tmp_unzip_path, unzip_path)
    
    @staticmethod
    def _get_filename_from_url(url):
        """
        Extracts the filename from a given URL, ignoring query parameters and fragments.

        :param url: The URL from which to extract the filename.
        :type url: str
        :return: The filename (last part of the URL path) or an empty string if no filename exists.
        :rtype: str

        :Example:

        >>> get_filename_from_url("https://example.com/path/to/file.txt?param=value")
        'file.txt'
        >>> get_filename_from_url("https://example.com/path/to/")
        ''
        """
        parsed_url = urlparse(url)
        return parsed_url.path.rsplit('/', 1)[-1]
    
    def download(self, 
                 url: str, 
                 dataset_name: str, 
                 saved_filename: str = None) -> None:
        """
        Downloads a file from the given URL and unpacks it into a folder based on 
        the dataset_name, and optionally a subfolder_name, using the download_path as the base path.

        :param url: URL to download the ZIP file from.
        :param dataset_name: The name of the dataset (used for directory naming).
        :param saved_filename: File name to give to the download. If not provided then the filename
            will be based on the filename in the URL. Use this parameter when the URL provides no
            useful name
        """
        if saved_filename:
            filename = saved_filename
        else:
            filename = self._get_filename_from_url(url)
        dest_path = os.path.join(self.download_path, dataset_name, filename)

        if os.path.exists(dest_path):
            print(f"Skipping {dataset_name} as unzip path exists: {dest_path}")
        else:
            self._download(url, dest_path)
                
    def download_and_unzip(self, 
                       url: str, 
                       dataset_name: str, 
                       subfolder_name: str = None, 
                       flatten_directory: bool = False) -> None:
        """
        Downloads a ZIP file from the given URL and unpacks it into a folder based on 
        the dataset_name, and optionally a subfolder_name, using the download_path as the base path.
        
        If flatten_directory is True:
        - After unzipping, if the ZIP contains exactly one top-level folder,
            its contents are moved up one level (into dataset_name or dataset_name/subfolder).
        - If there is more than one top-level entry, an error is thrown indicating
            that flattening cannot be performed. The error includes the unzip path,
            a listing of its contents, and the download URL to help with debugging.
        
        Before downloading, the function checks if the output folder (dataset_name or dataset_name/subfolder)
        already exists, and if so, skips the download.
        
        :param url: URL to download the ZIP file from.
        :param dataset_name: The name of the dataset (used for directory naming).
        :param subfolder_name: Optional subfolder to further differentiate downloads.
        :param flatten_directory: If True, and if the ZIP contains a single top-level folder,
                                that folder will be flattened (its contents moved up one level).
        """
        base_path = os.path.join(self.download_path, dataset_name)
        unzip_path = os.path.join(base_path, subfolder_name if subfolder_name else "")

        # Check if the output folder already exists to avoid redundant downloads.
        if os.path.exists(unzip_path):
            print(f"Skipping {dataset_name}/{subfolder_name or ''} as unzip path exists: {unzip_path}")
            return

        

        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the ZIP file to a temporary location
            zip_file_path = os.path.join(temp_dir, f"{dataset_name}.zip")
            self._download(url, zip_file_path)

            # Unzip the file into the designated unzip_path. This creates the upzip_path if it doesn't exist.
            self.unzip(zip_file_path, unzip_path, "")

        # If flattening is enabled, inspect and flatten the directory if appropriate.
        if flatten_directory:
            # List items in the unzip_path
            items = os.listdir(unzip_path)
            # Check if there's exactly one item and it's a directory.
            if len(items) == 1 and os.path.isdir(os.path.join(unzip_path, items[0])):
                single_dir = os.path.join(unzip_path, items[0])
                for item in os.listdir(single_dir):
                    shutil.move(os.path.join(single_dir, item), unzip_path)
                os.rmdir(single_dir)
                print(f"Flattening complete: {dataset_name}/{subfolder_name or ''}")
            else:
                # Build a detailed error message for debugging purposes.
                contents_listing = os.listdir(unzip_path)
                error_message = (
                    f"Cannot flatten directory: ZIP file contains more than a single top-level folder.\n"
                    f"Unzip path: '{unzip_path}'\n"
                    f"Contents: {contents_listing}\n"
                    f"Download URL: {url}\n"
                    f"Please verify the structure of the downloaded ZIP file."
                )
                raise ValueError(error_message)



    def move_files(self, 
                   patterns: List[str], 
                   source_directory: str, 
                   destination_directory: str) -> None:
        """
        Moves files from a source directory to a destination directory based on 
        the provided file-matching patterns.

        :param patterns: A list of file patterns (e.g., ["*.csv", "*.txt"]).
        :param source_directory: The directory to scan for files matching the patterns.
        :param destination_directory: The target directory to which the matched files will be moved.
        """
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)
            print(f'Making destination directory {destination_directory}')

        # Find and move files matching the patterns
        for pattern in patterns:
            for filepath in glob.glob(os.path.join(source_directory, pattern)):
                filename = os.path.basename(filepath)
                destination_filepath = os.path.join(destination_directory, filename)
                shutil.move(filepath, destination_filepath)
                print(f"Moved {filepath} to {destination_filepath}")

    def download_unzip_keep_subset(self, 
                                   url: str, 
                                   zip_file_patterns: List[str], 
                                   dataset_name: str) -> None:
        """
        Downloads a ZIP file from the given URL, unpacks it into a temporary directory, 
        and moves only a subset of files (matching the given patterns) into a final directory.

        :param url: The URL of the ZIP file to download.
        :param zip_file_patterns: A list of glob patterns for files to retain.
        :param dataset_name: The name of the dataset (used for directory naming).
        """
        unzip_path = os.path.join(self.download_path, dataset_name)
        if os.path.exists(unzip_path):
            print(f"Skipping {dataset_name} as unzip path exists: {unzip_path}")
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_file_path = os.path.join(temp_dir, f"{dataset_name}.zip")
                print(f'Downloading to {zip_file_path}')
                self._download(url, zip_file_path)

                extract_path = os.path.join(temp_dir, dataset_name)
                self.unzip(zip_file_path, extract_path, extract_path)

                # Only keep a subset of the files to limit the storage used
                self.move_files(zip_file_patterns, extract_path, unzip_path)
        # Outside the block, the temporary directory and its contents will be automatically deleted

    def create_virtual_raster(self, dataset_name: str, layer: str = None, vrt_filename: str = None) -> None:
        """
        Creates a virtual raster (VRT) from GeoTiff images found in the specified dataset folder 
        or subfolder (layer). The VRT file is created in the dataset folder (download_path/dataset_name),
        even if the images are located in a subfolder.

        :param dataset_name: The name of the dataset (base folder) within download_path.
        :param layer: Optional. The subfolder name within the dataset that contains the GeoTiff images.
                      If not provided, the function will search the base dataset folder.
        :param vrt_filename: Optional. The output filename for the VRT. If not provided, defaults to 
                             '<layer>.vrt' (if layer is provided) or '<dataset_name>.vrt' otherwise,
                             and is created in the dataset folder.
        """
        # Determine the folder to search for GeoTiff images.
        if layer:
            target_folder = os.path.join(self.download_path, dataset_name, layer)
        else:
            target_folder = os.path.join(self.download_path, dataset_name)
        
        if not os.path.exists(target_folder):
            print(f"Target folder does not exist: {target_folder}")
            return

        # Set the VRT file to be in the dataset folder.
        dataset_folder = os.path.join(self.download_path, dataset_name)
        if vrt_filename is None:
            vrt_name = layer if layer else dataset_name
            vrt_filename = os.path.join(dataset_folder, f"{vrt_name}.vrt")
        else:
            # If a relative path is provided, assume it's relative to the dataset folder.
            if not os.path.isabs(vrt_filename):
                vrt_filename = os.path.join(dataset_folder, vrt_filename)
        
        # Skip creation if the VRT already exists.
        if os.path.exists(vrt_filename):
            print(f"Virtual raster already exists at {vrt_filename}. Skipping creation.")
            return

        # Search for GeoTiff images in the target folder.
        tiff_patterns = ["*.tif", "*.tiff"]
        geotiff_files = []
        for pattern in tiff_patterns:
            geotiff_files.extend(glob.glob(os.path.join(target_folder, pattern)))
            
        if not geotiff_files:
            print(f"No GeoTiff files found in {target_folder}")
            return

        print(f"Creating virtual raster at {vrt_filename}")
        print(f"Using {len(geotiff_files)} files from {target_folder}")

        # Create the virtual raster using GDAL.
        vrt = gdal.BuildVRT(vrt_filename, geotiff_files)
        if vrt is None:
            print("Failed to create virtual raster")
        else:
            print("Virtual raster created successfully")
            # Close the dataset.
            vrt = None


