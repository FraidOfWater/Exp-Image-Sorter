@echo off
setlocal

:: Set the name of the folder to delete
set "folderToDelete=dist"
set "folderToDelete2=build"
if exist "%folderToDelete%" (
    rmdir /s /q "%folderToDelete%"
    echo Deleted folder: %folderToDelete%
) else (
    echo Folder not found: %folderToDelete%
)
if exist "%folderToDelete2%" (
    rmdir /s /q "%folderToDelete2%"
    echo Deleted folder: %folderToDelete2%
) else (
    echo Folder not found: %folderToDelete2%
)

pyinstaller sortimages_multiview.py --name SIME-QOL --noconfirm

:: Set the name of the file to copy and the destination for the file
set "fileToCopy=libvlc.dll"  :: Change this to your actual file name
set "fileDestination=dist\SIME-QOL\_internal\libvlc.dll"  :: Change this to your actual destination folder

:: Set the name of the file to copy and the destination for the file
set "fileToCopy2=libvlccore.dll"  :: Change this to your actual file name
set "fileDestination2=dist\SIME-QOL\_internal\libvlccore.dll"  :: Change this to your actual destination folder

:: Set the name of the file to copy and the destination for the file
set "fileToCopy3=themes.json"  :: Change this to your actual file name
set "fileDestination3=dist\SIME-QOL\themes.json"  :: Change this to your actual destination folder

:: Set the name of the file to copy and the destination for the file
set "folderToCopy=vips-dev-8.16"  :: Change this to your actual file name
set "folderCopyDestination=dist\SIME-QOL\_internal\vips-dev-8.16"  :: Change this to your actual destination folder

:: Set the name of the file to copy and the destination for the file
set "folderToCopy2=plugins"  :: Change this to your actual file name
set "folderCopyDestination2=dist\SIME-QOL\_internal\plugins"  :: Change this to your actual destination folder

:::::: Copy the file to the destination folder
if exist "%fileToCopy%" (
    copy "%fileToCopy%" "%fileDestination%"
    echo Copied file: %fileToCopy% to %fileDestination%
) else (
    echo File not found: %currentDir%\%fileToCopy%
)
if exist "%fileToCopy2%" (
    copy "%fileToCopy2%" "%fileDestination2%"
    echo Copied file: %fileToCopy2% to %fileDestination2%
) else (
    echo File not found: %currentDir%\%fileToCopy2%
)
if exist "%fileToCopy3%" (
    copy "%fileToCopy3%" "%fileDestination3%"
    echo Copied file: %fileToCopy3% to %fileDestination3%
) else (
    echo File not found: %currentDir%\%fileToCopy3%
)

:::: Copy the folder to the destination folder
if exist "%folderToCopy%" (
    xcopy "%folderToCopy%\*" "%folderCopyDestination%" /s /e /i /y
    echo Copied folder: %folderToCopy% to %folderCopyDestination%
) else (
    echo Folder not found: %folderToCopy%
)
if exist "%folderToCopy2%" (
    xcopy "%folderToCopy2%\*" "%folderCopyDestination2%" /s /e /i /y
    echo Copied folder: %folderToCopy2% to %folderCopyDestination2%
) else (
    echo Folder not found: %folderToCopy2%
)

endlocal
pause
