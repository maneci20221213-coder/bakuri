typedef unsigned short WCHAR;
typedef unsigned int DWORD;
typedef void* HANDLE;
typedef int BOOL;
typedef struct {DWORD cb;WCHAR *reserved,*desktop,*title;DWORD x,y,xs,ys,xc,yc,fill,flags;unsigned short show,reserved2;void* bytes;HANDLE in,out,err;} STARTUPINFO;
typedef struct {HANDLE process,thread;DWORD pid,tid;} PROCESSINFO;
extern DWORD GetModuleFileNameW(HANDLE,WCHAR*,DWORD);
extern WCHAR* GetCommandLineW(void);
extern BOOL CreateProcessW(WCHAR*,WCHAR*,void*,void*,BOOL,DWORD,void*,WCHAR*,STARTUPINFO*,PROCESSINFO*);
extern DWORD WaitForSingleObject(HANDLE,DWORD);
extern BOOL GetExitCodeProcess(HANDLE,DWORD*);
extern BOOL CloseHandle(HANDLE);
extern void ExitProcess(DWORD);
extern int MessageBoxW(HANDLE,const WCHAR*,const WCHAR*,unsigned int);
_Static_assert(sizeof(DWORD)==4,"DWORD");
_Static_assert(sizeof(STARTUPINFO)==104,"STARTUPINFO");
static WCHAR base[32768],exe[32768],command[32768];
static unsigned int append(WCHAR* out,unsigned int pos,const WCHAR* value){while(*value&&pos<32766)out[pos++]=*value++;out[pos]=0;return pos;}
void entry(void){
 DWORD n=GetModuleFileNameW(0,base,32768);if(!n||n>=32768)ExitProcess(1);
 while(n&&base[n-1]!=92)n--;base[n]=0;
 unsigned int p=append(exe,0,base);append(exe,p,(const WCHAR*)u"runtime\\pythonw.exe");
 p=append(command,0,(const WCHAR*)u"\"");p=append(command,p,exe);p=append(command,p,(const WCHAR*)u"\" \"");p=append(command,p,base);p=append(command,p,(const WCHAR*)u"app.py\" ");
 WCHAR* args=GetCommandLineW();if(*args==34){args++;while(*args&&*args!=34)args++;if(*args)args++;}else while(*args&&*args!=32&&*args!=9)args++;
 append(command,p,args);
 STARTUPINFO si={0};PROCESSINFO pi={0};si.cb=sizeof(si);
 if(!CreateProcessW(exe,command,0,0,0,0,0,base,&si,&pi)){MessageBoxW(0,(const WCHAR*)u"Could not start the included Python runtime. Extract the entire ZIP to a folder and keep the runtime folder beside this EXE.",(const WCHAR*)u"Bakuri",16);ExitProcess(2);}
 CloseHandle(pi.thread);WaitForSingleObject(pi.process,0xffffffff);DWORD code=1;GetExitCodeProcess(pi.process,&code);CloseHandle(pi.process);ExitProcess(code);
}
