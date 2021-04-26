# aggrokatz
![aggro_card](https://user-images.githubusercontent.com/19204702/116058797-7d1cdb80-a680-11eb-9287-f888e860e6c4.jpg)
# What is this
`aggrokatz` is an Aggressor plugin extension for [`CobaltStrike`](https://www.cobaltstrike.com) which enables [`pypykatz`](https://github.com/skelsec/pypykatz) to interface with the beacons remotely.  
The current version of `aggrokatz` allows `pypykatz` to parse LSASS dump files and Registry hive files to extract credentials and other secrets stored without downloading the file and without uploading any suspicious code to the beacon (CS is already there anyhow).
In the future this project aims to provide additional features for covert operations suchs as searching and decrypting all DPAPI secrets/kerberoasting/etc...

# IMPORTANT NOTES - PLEASE READ THIS
LSASS/Registry dumping is not the goal of this project, only parsing. Reasons: 
 1. Multiple techniques for dumping are already implemented from CS and widely available to the public. 
 2. We want to keep our dumping technique private.

In CS client, do not use "reload" nor try to manually unload then reload the script if you modified it. You MUST unload it, close the client and start it anew, then load the modified script. Otherwise you will have multiple versions running simultaneously and a ton of errors and weird behaviours will happen!  
While parsing lsass/registry files on the remote end please don't interact with the specific beacon you started the script on. Normally it wouldn't cause any problems, but I can't give any guarantees.

# Install
 - You will need [`pycobalt`](https://github.com/dcsync/pycobalt) installed and set up. There is a readme on their github page.  
 - You will need to install [`pypykatz`](https://github.com/skelsec/pypykatz/) version must be `>=0.4.8`
 - You will need cobaltstrike

# Setup
 - make sure that pycobalt's `aggressor.cna` file is set up and is aware of your python interpreter's location
 - Change the pycobalt_path in `aggrokatz.cna` to point to `pycobalt.cna`
 - in CS use the `View > Script Console` and `Cobalt Strike > Script Manager` windows. Using `Script Manager` load the `aggkatz.cna` script.

# Usage
 - If the `aggkatz.cna` script loaded successfully you will have a new menu item `pypykatz` when right-clicking on a beacon.
 - During parsing you will see debug messages in `Script Console` window.
 - After parsing is finished, the results will be displayed in both `Script Console` window and the Beacon's own window.

### LSASS dump parse menu parameters
 - `LSASS file`: The location of the `lsass.dmp` file on the remote computer. You can also use UNC paths to access shared `lsass.dmp` files over SMB 
 - `chunksize` : The maximum amount that will be read in one go
 - `BOF file`  : The BOF file (Beacon Object File) which allows chunked reads. This file will be uploaded and executed (in-memory) each time a new chunk is being read.
 - `(module)`  : Specifies which modules will be parsed. Default: `all`
 - `Output`    : Specifies the output format(s)
 - `Populate Credential tab` : After a sucsessful parsing all obtained credentials will be available on the Cobalt Srike's Credential tab. This feature is in beta
 - `Delete remote file after parsing` : After a sucsessful parsing the LSASS dump file will be removed from the target

### Registry dump parse menu parameters
 - `SYSTEM file`: The location of the `SYSTEM.reg` file on the remote computer. You can also use UNC paths to access shared files over SMB 
 - `SAM file (optional)`: The location of the `SAM.reg` file on the remote computer. You can also use UNC paths to access shared files over SMB 
 - `SECURITY file (optional)`: The location of the `SECURITY.reg` file on the remote computer. You can also use UNC paths to access shared files over SMB 
 - `SOFTWARE file (optional)`: The location of the `SOFTWARE.reg` file on the remote computer. You can also use UNC paths to access shared files over SMB 
 - `chunksize` : The maximum amount that will be read in one go
 - `BOF file`  : The BOF file (Beacon Object File) which allows chunked reads. This file will be uploaded and executed (in-memory) each time a new chunk is being read.
 - `Output`    : Specifies the output format(s)

# Limitations
The file read BOF currently supports file reads up to 4Gb. This can be extended with some modifications but so far such large files haven't been observed.

# How it works
## TL;DR 
Normally `pypykatz`'s parser performs a series of file read operations on disk, but with the help of aggrokatz these read operations are tunneled to the beacon using a specially crafted BOF (Beacon Object File) which allows reading the remote file contents in chunks. This allows `pypykatz` to extract all secrets from the remote files without reading the whole file, only grabbing the necessary chunks where the secrets are located.

## In-depth  
To get the full picture of the entire process, there are two parts we'd need to highlight:
 1. how `pypykatz` integrates with `CobaltStrike`
 2. how `pypykatz` performs the credential extraction without reading the whole file

### pypykatz integration to CobaltStrike
CobaltStrike (agent) is written in Java, pypykatz is written in python. This is a problem. Lucky for us an unknown entity has created [`pycobalt`](https://github.com/dcsync/pycobalt) which provides a neat interface between the two worlds complete with usefule APIs which can be invoked directly from python. Despite `pycobalt` being a marvellous piece of engineering, there are some problems/drawbacks with it that we need to point out:
 1. About trusting the `pycobalt` project:
  - We have tried to reach out to the author but we got no reply.
  - We cannot guarantee that the `pycobalt` project will be maintained in the future.
  - We do not control any aspect of `pycobalt`'s development.
 2. About technical issues observed:
  - Generally there are some encoding issues between `pycobalt` and `CobaltSrike`. This results in some API calls which would return bytes that can't be used because some bytes get mangled by the encoder. By checking the code we conclude that most encoding/decoding issues are because `pycobalt` uses STDOUT/STDIN to communicate with the Java process 
  - Specifically the [`bof_pack`](https://www.cobaltstrike.com/aggressor-script/functions.html#bof_pack) API call which is crucial for this project had to be implemented as a pure-aggressor script and only invoked from python using basic data structures (string and int) and not using bytes.
  - Only blocking APIs provided by the `pycobalt` package without threading support. Well, at least we observed that threading breaks randomly, but we kinda expected this.
  - Blocking API + no threading + relying on callbacks = we had to employ some weird hacks to get it right. 

### Credential parsing on a stack of cards
`pypykatz` and it's companion module `minidump` had to be modified to allow a more efficient chunked parsing than what was implemented before, but this is a topic for another day.   
After `pypykatz` was capable to interface with `CobaltStrike` via `pycobalt` the next step was to allow chunked file reading. Sadly this feature is not available by-default on any of the C2 solutions we have seen, so we had to implement it. The way we approached this problem is by implementing chunked reading via the use of `CobaltStrike`'s [Beacon Object Files interface](https://www.cobaltstrike.com/help-beacon-object-files), BOF for short. BOFs are C programs that run on the beacon not as a separate executable but as a part of the already running beacon. This interface is super-useful because it makes BOFs much stealthier since all of the code executes in memory without anything being written to disk.  
Our BOF solution is a simple function and takes 4 arguments: 
 - `fileName` : Full file path of the LSASS dump file or registry hive (on the remote end) 
 - `buffsize` : Amount (in bytes) to be read from the file
 - `seekSize` : The position where the file read operation should start from (from the beginning of the file)
 - `rplyid`   : An identification number to be incorporated in the reply to avoid possible collisions

With these parameters, `pypykatz` (running on the agent) can issue file read operations on the beacon (target computer) that specifically target certain parts of the file.  
On the other end (in CobaltStrike) `aggrokatz` registers a callback to monitor every message returned by the target beacon. If the message's header matches the header of a file read operation it will be processed as a chunk of a `minidump` file and will be dispatched to the `minidump` parser which will dispatch the result to `pypykatz`. In case more read is needed `pypykatz` will issue a read using the `minidump` reader that will dispatch a new read command on the beacon via the BOF interface. This process repeats until the file is parsed.

### Results
After parsing around a 100 LSASS dumps using this method, we can state the following (chunk size used was 20k):
 - Depending on the LSASS dump file size (our dumps were between 40Mb - 300Mb) on average all secrets could be extraced using 3,5Mb. Note that this number does not depend on the size of the LSASS dump rather than on the amount of secrets and the amount of packages you select to be parsed.
 - On average 250 read operations were used for a successful parse. 
 - Time to parse only relies on your jitter/sleep configuration so measuring it is pointless.

### Drawbacks
 - For each read operation a BOF needs to be uploaded to the beacon. (we secretly hope someone from CobaltSrike will look at this article and decide to implement basic file reading operations as a default, so we can skip using this solution)
 - The number of read operations can be problematic if you are using a beacon with a really large jitter/sleep.

# Kudos
dcsync - author of [`pycobalt`](https://github.com/dcsync/pycobalt)  
Nicol Jos [`@shinepaw`](https://twitter.com/shinepaw) - logo design
