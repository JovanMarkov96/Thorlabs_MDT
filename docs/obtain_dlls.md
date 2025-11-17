# Obtaining Thorlabs MDT DLLs

This project uses the Thorlabs MDT SDK DLLs for optional SDK-backed functionality.
Those DLLs are vendor-supplied and may be proprietary. For legal and practical
reasons the repository does not include the DLL binaries; instead follow the
instructions below to obtain and install them locally.

Important: read the Thorlabs End-user License (included in `docs/licenses/`) before
downloading or redistributing binaries.

Steps
1. Visit the official Thorlabs software pages for the MDT controllers. For example:

   - General MDT download page: https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=MDT69xB
   - Specific MDT693A page (older link): https://www.thorlabs.com/software_pages/viewsoftwarepage.cfm?code=MDT693A

2. Download the appropriate MDT SDK package for your platform (Windows x86/x64).

3. Locate the DLL files in the downloaded package. The project expects the
   runtime DLL(s) to be placed in the project folder `./.mdt_dlls/` (create this
   directory if it does not exist). Example filenames:

   - `MDT_COMMAND_LIB.dll` (32-bit)
   - `MDT_COMMAND_LIB_x64.dll` (64-bit) or similar

4. Verify the EULA and place the DLL(s) under the `.mdt_dlls/` directory.

5. Optionally compute and verify SHA256 checksums:

```powershell
# Compute checksum on Windows PowerShell
Get-FileHash .\.mdt_dlls\MDT_COMMAND_LIB.dll -Algorithm SHA256
```

6. Run the project. The code will attempt to load the DLL(s) from `./.mdt_dlls/`.

Automated helper
-----------------
The repository contains an optional helper script `tools/get_mdt_dlls.py` that
can download DLLs when provided with direct download URLs and verify checksums.
It will NOT commit or upload the binaries to the repository.

Legal note
----------
The Thorlabs EULA allows making copies and giving copies to others as long as
the EULA text and copyright/proprietary notices accompany the binaries. If you
intend to redistribute binaries (for example, in a release), ensure you include
the full EULA text and comply with any redistribution conditions. When in doubt,
contact Thorlabs support for clarification.
