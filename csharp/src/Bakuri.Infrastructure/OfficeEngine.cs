using System.Runtime.InteropServices;
using Microsoft.Win32;
using Bakuri.Core;
namespace Bakuri.Infrastructure;

/// <summary>Owned by one job's STA thread. Uses CoCreateInstance rather than GetActiveObject; never quits a possibly shared pre-existing application.</summary>
public sealed class OfficeEngine : IDisposable {
    readonly Dictionary<string,object> apps=new();
    readonly HashSet<string> safeToQuit=new();
    dynamic App(string id) {
        if(apps.TryGetValue(id,out var existing))return existing;
        string processName=id switch{"Word.Application"=>"WINWORD","Excel.Application"=>"EXCEL","PowerPoint.Application"=>"POWERPNT",_=>"Hwp"};
        var existingProcesses=System.Diagnostics.Process.GetProcessesByName(processName);bool alreadyRunning=existingProcesses.Length>0;foreach(var process in existingProcesses)process.Dispose();
        if(!alreadyRunning)safeToQuit.Add(id);
        var type=Type.GetTypeFromProgID(id)??throw new IOException("필요한 한글 또는 Office 프로그램을 설치해 주세요.");
        dynamic app=Activator.CreateInstance(type)??throw new IOException("문서 프로그램을 실행하지 못했습니다.");apps[id]=app;
        if(id=="Word.Application"||id=="Excel.Application"){app.Visible=false;app.DisplayAlerts=0;app.AutomationSecurity=3;}
        if(id=="PowerPoint.Application"){app.AutomationSecurity=3;app.DisplayAlerts=1;}
        if(id=="HWPFrame.HwpObject")RegisterHancom(app);
        return app;
    }
    static void RegisterHancom(dynamic app) {
        string module=Path.Combine(AppContext.BaseDirectory,"FilePathCheckerModuleExample.dll");
        foreach(var view in new[]{RegistryView.Registry32,RegistryView.Registry64}) {
            using var root=RegistryKey.OpenBaseKey(RegistryHive.CurrentUser,view);using var key=root.CreateSubKey(@"Software\HNC\HwpAutomation\Modules");key.SetValue("BakuriCSharpTrial",module);
        }
        app.RegisterModule("FilePathCheckDLL","BakuriCSharpTrial");
    }
    static void Require(bool success,string message){if(!success)throw new IOException(message);}
    public void Export(string source,string target,OutputFormat format,CancellationToken cancel) {
        cancel.ThrowIfCancellationRequested();var ext=Path.GetExtension(source).ToLowerInvariant();dynamic? book=null;
        if(ext is ".doc" or ".docx"&&format==OutputFormat.Pdf) {
            dynamic app=App("Word.Application");try{book=app.Documents.Open(source,ReadOnly:true,AddToRecentFiles:false);book.ExportAsFixedFormat(target,17);}finally{if(book!=null){book.Close(false);Marshal.FinalReleaseComObject(book);}}
        }else if(ext is ".ppt" or ".pptx") {
            dynamic app=App("PowerPoint.Application");try{book=app.Presentations.Open(source,ReadOnly:true,Untitled:false,WithWindow:false);book.SaveAs(target,32);}finally{if(book!=null){book.Close();Marshal.FinalReleaseComObject(book);}}
        }else if(Capabilities.Sheets.Contains(ext)) {
            dynamic app=App("Excel.Application");try {
                if(ext is ".csv" or ".tsv") {
                    using var input=File.OpenRead(source);var bytes=new byte[(int)Math.Min(65536,input.Length)];input.ReadExactly(bytes);var utf8=new System.Text.UTF8Encoding(false,true);int origin;
                    try{utf8.GetDecoder().GetChars(bytes,0,bytes.Length,new char[bytes.Length],0,false);origin=65001;}catch(System.Text.DecoderFallbackException){origin=949;}
                    if(bytes.Length>=2&&(bytes[0]==255&&bytes[1]==254||bytes[0]==254&&bytes[1]==255))origin=1200;
                    app.Workbooks.OpenText(Filename:source,Origin:origin,DataType:1,TextQualifier:1,Tab:ext==".tsv",Comma:ext==".csv",Local:true);book=app.ActiveWorkbook;
                }else book=app.Workbooks.Open(source,UpdateLinks:0,ReadOnly:true,IgnoreReadOnlyRecommended:true);
                if(format==OutputFormat.Xlsx)book.SaveAs(target,FileFormat:51);else book.ExportAsFixedFormat(0,target,0,true,false);
            }finally{if(book!=null){book.Close(false);Marshal.FinalReleaseComObject(book);}}
        }else {
            dynamic app=App("HWPFrame.HwpObject");try{Require(app.Open(source,"",""),"한글 문서를 열지 못했습니다.");cancel.ThrowIfCancellationRequested();Require(app.SaveAs(target,format==OutputFormat.Docx?"OOXML":format.ToString().ToUpperInvariant(),""),"한글 문서를 저장하지 못했습니다.");}finally{app.Clear(1);}
        }
        cancel.ThrowIfCancellationRequested();Require(File.Exists(target),"변환 결과를 저장하지 못했습니다.");
    }
    public void MergeHancom(IReadOnlyList<string> files,string target,CancellationToken cancel) {
        dynamic app=App("HWPFrame.HwpObject");try {
            Require(app.Open(files[0],"",""),"첫 한글 문서를 열지 못했습니다.");
            foreach(var source in files.Skip(1)) {
                cancel.ThrowIfCancellationRequested();app.HAction.Run("MoveDocEnd");dynamic action=app.CreateAction("InsertFile"),set=action.CreateSet();action.GetDefault(set);
                set.SetItem("FileName",source);set.SetItem("FileFormat","");set.SetItem("FileArg","");foreach(var key in new[]{"KeepSection","KeepStyle","KeepCharshape","KeepParashape"})set.SetItem(key,1);
                Require(action.Execute(set)!=false,"한글 문서를 합치지 못했습니다.");
            }
            cancel.ThrowIfCancellationRequested();Require(app.SaveAs(target,"HWPX","")&&File.Exists(target),"통합본을 저장하지 못했습니다.");
        }finally{app.Clear(1);}
        HwpxLayout.Repack(target);
    }
    public void ImageDocument(IReadOnlyList<ImagePage> pages,string target,WorkDirectory work,bool pdfLayout,CancellationToken cancel) {
        if(pages.Count==0||pages.Count>65535)throw new IOException("문서에 넣을 페이지 수를 확인해 주세요.");
        dynamic app=App("HWPFrame.HwpObject");var staged=pages.Select(p=>p.ImagePath).ToArray();
        try {
            app.Clear(1);dynamic setup=app.CreateAction("PageSetup"),ps=setup.CreateSet();setup.GetDefault(ps);dynamic page=ps.CreateItemSet("PageDef","PageDef");
            foreach(var pair in new Dictionary<string,int>{{"PaperWidth",59528},{"PaperHeight",84189},{"LeftMargin",5669},{"RightMargin",5669},{"TopMargin",5669},{"BottomMargin",5669},{"HeaderLen",0},{"FooterLen",0},{"GutterLen",0},{"Landscape",0}})page.SetItem(pair.Key,pair.Value);
            ps.SetItem("ApplyTo",2);Require(setup.Execute(ps)!=false,"용지 설정에 실패했습니다.");
            dynamic action=app.CreateAction("TableCreate"),set=action.CreateSet();action.GetDefault(set);set.SetItem("Rows",pages.Count);set.SetItem("Cols",1);set.SetItem("WidthType",2);set.SetItem("HeightType",1);int width=48189;
            set.CreateItemArray("ColWidth",1).SetItem(0,width);dynamic heights=set.CreateItemArray("RowHeight",pages.Count);int total=0;
            for(int i=0;i<pages.Count;i++){int height=Math.Max(1,(int)Math.Round(width*pages[i].HeightPoints/pages[i].WidthPoints));heights.SetItem(i,height);total+=height;}
            dynamic props=set.CreateItemSet("TableProperties","Table");foreach(var pair in new Dictionary<string,int>{{"TreatAsChar",0},{"PageBreak",1},{"RepeatHeader",0},{"CellSpacing",0},{"CellMarginLeft",0},{"CellMarginRight",0},{"CellMarginTop",0},{"CellMarginBottom",0},{"HorzRelTo",2},{"HorzAlign",1},{"VertRelTo",2},{"VertAlign",0},{"FlowWithText",1},{"TextWrap",1},{"WidthRelTo",4},{"Width",width},{"HeightRelTo",2},{"Height",total},{"HoldAnchorObj",0},{"OutsideMarginLeft",0},{"OutsideMarginRight",0},{"OutsideMarginTop",0},{"OutsideMarginBottom",0}})props.SetItem(pair.Key,pair.Value);
            Require(action.Execute(set)!=false,"이미지 표 생성에 실패했습니다.");
            for(int i=0;i<pages.Count;i++) {
                cancel.ThrowIfCancellationRequested();dynamic picture=app.InsertPicture(staged[i],true,3,false,false,0,0,0);Require(picture!=null,"그림을 넣지 못했습니다.");dynamic properties=picture.Properties;properties.SetItem("TreatAsChar",1);picture.Properties=properties;app.HAction.Run("Cancel");if(i+1<pages.Count)app.HAction.Run("TableRightCell");
            }
            cancel.ThrowIfCancellationRequested();Require(app.SaveAs(target,"HWPX","")&&File.Exists(target),"그림 문서를 저장하지 못했습니다.");
        }finally{app.Clear(1);}
        if(pdfLayout)HwpxLayout.Paginate(target,pages);else HwpxLayout.Repack(target);
    }
    public void Slides(IReadOnlyList<ImagePage> pages,string target,WorkDirectory work,CancellationToken cancel) {
        dynamic app=App("PowerPoint.Application"),book=app.Presentations.Add(WithWindow:false);
        try {
            if(pages.Count==0)throw new IOException("슬라이드에 넣을 페이지가 없습니다.");
            book.PageSetup.SlideWidth=720;book.PageSetup.SlideHeight=Math.Clamp(720*pages[0].HeightPoints/pages[0].WidthPoints,72,4032);
            for(int i=0;i<pages.Count;i++) {
                cancel.ThrowIfCancellationRequested();var page=pages[i];double sw=book.PageSetup.SlideWidth,sh=book.PageSetup.SlideHeight,scale=Math.Min(sw/page.WidthPoints,sh/page.HeightPoints),width=page.WidthPoints*scale,height=page.HeightPoints*scale;
                dynamic slide=book.Slides.Add(i+1,12);slide.Shapes.AddPicture(page.ImagePath,false,true,(sw-width)/2,(sh-height)/2,width,height);
            }
            book.SaveAs(target,24);
        }finally{book.Close();Marshal.FinalReleaseComObject(book);}
    }
    public void Dispose(){foreach(var entry in apps){dynamic app=entry.Value;try{if(safeToQuit.Contains(entry.Key))app.Quit();}catch(Exception error){ConversionService.Log(error);}finally{Marshal.FinalReleaseComObject(app);}}apps.Clear();}
}
