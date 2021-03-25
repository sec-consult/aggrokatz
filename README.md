# aggrokatz

# IMPORTANT NOTES
In CS client, do not use "reload" nor try to manually unload then reload the script if you modified it. You MUST unload it, close the client and start it anew, then load the modified script. Otherwise you will have multiple versions running simultaniously and OMG a shitton of errors and weird behaviours will happen!!!!!!!  
While parsing lsass/registry files on the remote end please don't interact with the specific beacon you started the script on. Normally it wouldn't cause any problems, but I can't give any guarantees.

# Install
 - You will need [`pycobalt`](https://github.com/dcsync/pycobalt) installed and set up. There is a readme on their github page.  
 - You will need to install [`minidump`](https://github.com/skelsec/minidump/) Currently you must use the `speedup` branch
 - You will need to install [`pypykatz`](https://github.com/skelsec/pypykatz/) Currently you must use the `speedup` branch
 - You will need cobaltstrike

# Setup
 - make sure that pycobalt's `aggressor.cna` file is set up and is aware of your python interperer's location
 - Change the pycobalt_path in aggrokatz.cna to point to pycobalt.cna
 - in CS use the `View > Script Console` and `Cobalt Strike > Script Manager` windows. Using `Script Manager` load the `aggkatz.cna` script.

# Usage
 - If the `aggkatz.cna` script loaded sucsessfully you will have a new menu item `pypykatz` when right-clicking on a beacon.
 - During parsing you will see debug messages in `Script Console` window
 - After parsing finished the results will be displayed in both `Script Console` window and the Beacon's own window

# LSASS dump parse menu parameters
 - `LSASS file`: The location of the `lsass.dmp` file on the remote computer. You can also use UNC paths to access shared `lsass.dmp` files over SMB 
 - `chunksize` : The maximum amount that will be read in one go
 - `BOF file`  : The BOF file which allows chunked reads. this file will be uploaded and executed (in-memory) each time a new chunk is being read.
 - `(module)`  : Specifies which modules will be parsed. Default: `all`
 - `Output`    : Specifies the output format(s)
