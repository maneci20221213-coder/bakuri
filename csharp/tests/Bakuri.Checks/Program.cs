using System.Diagnostics;
using System.IO.Compression;
using System.Text.Json;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Bakuri.Core;
using Bakuri.Infrastructure;
using MuPDF.NET;

internal static class Program {
    static int checks;
    static void Check(bool value,string name){if(!value)throw new Exception("FAIL: "+name);checks++;Console.WriteLine("PASS: "+name);}
    static void Throws(Action action,string name){try{action();}catch{Check(true,name);return;}throw new Exception("FAIL: "+name);}
    [STAThread] static int Main(string[] args) {
        try {
            string root=Path.GetFullPath(args.ElementAtOrDefault(1)??Path.Combine(Path.GetTempPath(),"BakuriCSharpChecks-"+Guid.NewGuid().ToString("N")));Directory.CreateDirectory(root);
            if(args.FirstOrDefault()=="--benchmark"){Benchmark(root);return 0;}
            if(args.FirstOrDefault()=="--corpus"){Corpus(root);return 0;}
            Rules();Rename(root);ImagesAndPdf(root);Console.WriteLine($"Native checks passed: {checks}. Office/Hancom COM integration requires installed applications and is not covered on CI.");return 0;
        }catch(Exception error){Console.Error.WriteLine(error);return 1;}
    }
    static void Rules() {
        Check(Names.Insert("자료","서울",InsertPosition.Before)=="서울자료","per-file exact string insertion");
        Check(Names.Insert("자료_최종","3",InsertPosition.BeforeMarker,"최종","_")=="자료_3_최종","number marker and separators");
        Check(Names.FillDown("서울\n\n부산\n",4).SequenceEqual(new[]{"서울","서울","부산","부산"}),"clipboard fill preserves row assignments");
        Throws(()=>Names.FillDown("a\tb",1),"reject multiple clipboard columns");Throws(()=>Names.FillDown("a\nb",1),"reject extra clipboard rows");
        foreach(var name in new[]{"CON.txt","COM¹.pdf","a/b.pdf","a:b.pdf","name.","bad\u0001.pdf"})Check(Names.Validate(name).Length>0,"invalid Windows name "+name);
        Check(Names.Validate("한국어_😀.pdf")=="","Unicode filename");
        Check(Path.GetFileName(Names.Merged(new[]{@"C:\work\서울_1.pdf",@"C:\work\서울_2.pdf"},"pdf"))=="서울_통합본.pdf","shared merged name");
        Check(!Capabilities.Supports("photo.png",OutputFormat.Docx)&&Capabilities.Supports("photo.png",OutputFormat.Hwpx),"supported output intersection");
        Check(!Capabilities.CanMerge(new[]{"a.hwp","b.png"},OutputFormat.Hwpx),"reject mixed Hancom and image merging");
    }
    static void Rename(string root) {
        string directory=Path.Combine(root,"rename");Directory.CreateDirectory(directory);string a=Path.Combine(directory,"a.pdf"),b=Path.Combine(directory,"b.pdf");File.WriteAllText(a,"alpha");File.WriteAllText(b,"beta");
        var store=new FileStore();var journal=new JsonRenameJournal(Path.Combine(root,"rename-history.json"));var txn=new RenameTransaction(store,journal);var planner=new RenamePlanner(store);
        var files=new[]{new FileRule(new(Guid.NewGuid(),a),ManualName:"b.pdf"),new FileRule(new(Guid.NewGuid(),b),ManualName:"a.pdf")};var plan=planner.Preview(files,new());
        Check(plan.All(p=>p.Error==""),"preview permits safe filename swaps");txn.Apply(plan);Check(File.ReadAllText(a)=="beta"&&File.ReadAllText(b)=="alpha","two-phase filename swap keeps bytes");txn.Undo();Check(File.ReadAllText(a)=="alpha"&&File.ReadAllText(b)=="beta","undo restores original files");
        File.WriteAllText(Path.Combine(directory,"taken.pdf"),"external");var occupied=planner.Preview([new(new(Guid.NewGuid(),a),ManualName:"taken.pdf")],new());Check(occupied[0].Error.Length>0,"existing destination is blocked");Throws(()=>txn.Apply(occupied),"executor refuses invalid plan");
        var rename=planner.Preview([new(new(Guid.NewGuid(),a),ManualName:"new.pdf")],new());File.SetLastWriteTimeUtc(a,DateTime.UtcNow.AddSeconds(3));Throws(()=>txn.Apply(rename),"stale snapshot refused");
        var injected=new FailingStore(store);var rollback=new RenameTransaction(injected,new JsonRenameJournal(Path.Combine(root,"rollback.json")));var two=planner.Preview([new(new(Guid.NewGuid(),a)),new(new(Guid.NewGuid(),b))],new(Text:"renamed_"));Throws(()=>rollback.Apply(two),"partial move failure reported");Check(File.ReadAllText(a)=="alpha"&&File.ReadAllText(b)=="beta","failed rename rolls every file back");
        Check(!Directory.EnumerateFiles(directory,".bakuri-csharp-*").Any(),"rollback leaves no temporary files");
        string staged=Path.Combine(root,"staged.pdf");File.WriteAllText(staged,"result");var output=OutputPublisher.Publish(staged,a,CancellationToken.None);Check(output!=a&&File.ReadAllText(a)=="alpha","publisher never overwrites input");
        var cts=new CancellationTokenSource();cts.Cancel();Throws(()=>OutputPublisher.Publish(staged,Path.Combine(directory,"cancelled.pdf"),cts.Token),"cancelled output is not published");Check(!File.Exists(Path.Combine(directory,"cancelled.pdf")),"cancel leaves destination absent");
    }
    static void ImagesAndPdf(string root) {
        var bitmap=BitmapSource.Create(200,400,96,96,PixelFormats.Bgra32,null,Pixels(200,400),200*4);bitmap.Freeze();string png=Path.Combine(root,"pixel-test.png");Images.Save(bitmap,png);
        var bytes=File.ReadAllBytes(png);using var work=new WorkDirectory();var engine=new PdfEngine();string pdf=work.File("pdf");engine.FromImages(png,pdf,work,CancellationToken.None);
        using(var document=new Document(pdf)) {
            Check(document.PageCount==1,"PNG to PDF page count");Check(Math.Abs(document[0].Rect.Width-96)<0.01&&Math.Abs(document[0].Rect.Height-192)<0.01,"portrait PDF size follows pixel aspect");
            var embedded=document.ExtractImage(document.GetPageImages(0)[0].Xref);string extracted=work.File("png");File.WriteAllBytes(extracted,embedded.Image);Check(PixelBytes(Images.Load(extracted)[0]).SequenceEqual(PixelBytes(bitmap)),"PNG to PDF embedded pixels are lossless");
        }
        Check(File.ReadAllBytes(png).SequenceEqual(bytes),"conversion leaves original PNG unchanged");
        string merged=work.File("pdf");engine.Merge([pdf,pdf],merged,CancellationToken.None);Check(engine.PageCount(merged)==2,"PDF merge page count");
        var rendered=engine.Render(merged,work,150,CancellationToken.None);Check(rendered.Count==2&&rendered[0].WidthPoints<rendered[0].HeightPoints,"PDF render keeps portrait geometry");
        Check(File.Exists(rendered[0].ImagePath),"raster pages are disk-backed, not retained bitmaps");
        var service=new ConversionService(new StaRunner());var result=service.RunAsync(new([new(Guid.NewGuid(),png)],OutputFormat.Jpeg),new Progress<JobProgress>(),CancellationToken.None).GetAwaiter().GetResult();Check(result.Files.Count==1&&result.Files[0].Outcome==FileOutcome.Saved,"native conversion coordinator produces JPEG");
        string packed=work.File("hwpx");using(var zip=ZipFile.Open(packed,ZipArchiveMode.Create)){foreach(var (name,data) in new[]{("mimetype","application/hwp+zip"),("Contents/section0.xml","<section/>"),("BinData/image.dat",new string('x',10000))}){var entry=zip.CreateEntry(name,CompressionLevel.NoCompression);using var writer=new StreamWriter(entry.Open());writer.Write(data);}}
        long before=new FileInfo(packed).Length;HwpxLayout.Repack(packed);using(var zip=ZipFile.OpenRead(packed)){Check(zip.Entries.Count==3,"streamed HWPX repack keeps every member");using var reader=new StreamReader(zip.GetEntry("BinData/image.dat")!.Open());Check(reader.ReadToEnd()==new string('x',10000),"streamed HWPX repack preserves binary member");}Check(new FileInfo(packed).Length<before,"HWPX repack reduces uncompressed ZIP size");
    }
    static byte[] PixelBytes(BitmapSource bitmap){var converted=new FormatConvertedBitmap(bitmap,PixelFormats.Bgra32,null,0);var bytes=new byte[converted.PixelWidth*converted.PixelHeight*4];converted.CopyPixels(bytes,converted.PixelWidth*4,0);return bytes;}
    static byte[] Pixels(int width,int height){var pixels=new byte[width*height*4];for(int i=0;i<pixels.Length;i+=4){pixels[i]=(byte)((i/4)%251);pixels[i+1]=(byte)((i/width)%233);pixels[i+2]=180;pixels[i+3]=255;}return pixels;}
    static void Corpus(string root){Directory.CreateDirectory(root);for(int i=0;i<12;i++){var bitmap=BitmapSource.Create(1600,1200,96,96,PixelFormats.Bgra32,null,Pixels(1600,1200),1600*4);Images.Save(bitmap,Path.Combine(root,$"sample_{i:00}.png"));}}
    static void Benchmark(string root) {
        var paths=Directory.EnumerateFiles(root,"sample_*.png").OrderBy(p=>p).ToArray();var output=Path.Combine(root,"native-output");Directory.CreateDirectory(output);var copy=paths.Select(p=>{string path=Path.Combine(output,Path.GetFileName(p));File.Copy(p,path,true);return new InputFile(Guid.NewGuid(),path);}).ToArray();
        var service=new ConversionService(new StaRunner());var progress=new Progress<JobProgress>();var timing=Stopwatch.StartNew();var report=service.RunAsync(new(copy,OutputFormat.Pdf,true),progress,CancellationToken.None).GetAwaiter().GetResult();timing.Stop();
        if(report.Files.Any(f=>f.Outcome!=FileOutcome.Saved)||report.Files.Count!=1)throw new Exception("Benchmark conversion failed: "+JsonSerializer.Serialize(report));
        var data=new{Engine="C# / MuPDF.NET 3.28.2.4",Files=copy.Length,ElapsedMs=timing.Elapsed.TotalMilliseconds,OutputBytes=report.Files.Sum(f=>f.After),PeakWorkingSetBytes=Process.GetCurrentProcess().PeakWorkingSet64,OfficeTested=false};
        File.WriteAllText(Path.Combine(root,"native-benchmark.json"),JsonSerializer.Serialize(data,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(data));
    }
    sealed class FailingStore(IFileStore inner):IFileStore {int moves;public FileStamp Inspect(string p)=>inner.Inspect(p);public bool Exists(string p)=>inner.Exists(p);public IEnumerable<string> FilesIn(string p)=>inner.FilesIn(p);public void Move(string a,string b){if(++moves==4)throw new IOException("Injected move failure");inner.Move(a,b);}}
}
