using System.Diagnostics;
using System.Windows.Media.Imaging;
using Bakuri.Core;
namespace Bakuri.Infrastructure;

public sealed class ConversionService(StaRunner runner) : IConversionService {
    public Task<JobReport> RunAsync(JobRequest request,IProgress<JobProgress> progress,CancellationToken cancellation)=>runner.Run(()=>Run(request,progress,cancellation),cancellation);
    JobReport Run(JobRequest request,IProgress<JobProgress> progress,CancellationToken cancel) {
        if(request.Files.Count==0||request.Files.Any(f=>!Capabilities.Supports(f.Path,request.Format)))throw new ArgumentException("선택한 파일과 출력 형식을 확인해 주세요.");
        if(request.Merge&&!Capabilities.CanMerge(request.Files.Select(f=>f.Path),request.Format))throw new ArgumentException("이 파일은 선택한 형식으로 합칠 수 없습니다.");
        var clock=Stopwatch.StartNew();var results=new List<FileResult>();using var work=new WorkDirectory();using var office=new OfficeEngine();var pdf=new PdfEngine();bool cancelled=false;
        IReadOnlyList<ImagePage> Pages(IReadOnlyList<string> paths) {
            var all=new List<ImagePage>();foreach(var path in paths){cancel.ThrowIfCancellationRequested();if(Path.GetExtension(path).Equals(".pdf",StringComparison.OrdinalIgnoreCase))all.AddRange(pdf.Render(path,work,request.Format==OutputFormat.Hwpx?300:request.Dpi,cancel));else all.AddRange(Images.Load(path).Select(b=>new ImagePage(Images.CanEmbedOriginal(path)?path:Images.Stage(b,work),b.PixelWidth*72d/150,b.PixelHeight*72d/150)));}return all;
        }
        string AsPdf(string source){if(Path.GetExtension(source).Equals(".pdf",StringComparison.OrdinalIgnoreCase))return source;var target=work.File("pdf");if(Capabilities.IsImage(source))pdf.FromImages(source,target,work,cancel);else office.Export(source,target,OutputFormat.Pdf,cancel);return target;}
        void Publish(string source,string staged,string preferred,long before=0) {cancel.ThrowIfCancellationRequested();var target=OutputPublisher.Publish(staged,preferred,cancel);results.Add(new(source,target,FileOutcome.Saved,before,new FileInfo(target).Length,"저장 완료"));}
        try {
            foreach(var f in request.Files)new FileStore().Inspect(f.Path);
            if(request.Merge) {
                var paths=request.Files.Select(f=>f.Path).ToArray();var target=work.File(Capabilities.Extension(request.Format));progress.Report(new(10,"통합 문서 준비"));
                if(request.Format==OutputFormat.Pdf)pdf.Merge(paths.Select(AsPdf).ToArray(),target,cancel);
                else if(request.Format==OutputFormat.Hwpx&&paths.All(Capabilities.IsHancom))office.MergeHancom(paths,target,cancel);
                else if(request.Format==OutputFormat.Hwpx)office.ImageDocument(Pages(paths),target,work,paths.Any(p=>Path.GetExtension(p).Equals(".pdf",StringComparison.OrdinalIgnoreCase)),cancel);
                else office.Slides(Pages(paths),target,work,cancel);
                Publish(paths[0],target,Names.Merged(paths,Capabilities.Extension(request.Format)));progress.Report(new(100,"완료"));
            }else for(int index=0;index<request.Files.Count;index++) {
                var source=request.Files[index].Path;cancel.ThrowIfCancellationRequested();progress.Report(new(index*100/request.Files.Count,$"{index+1}/{request.Files.Count} · {Path.GetFileName(source)}"));
                try {
                    var target=work.File(Capabilities.Extension(request.Format));var ext=Path.GetExtension(source).ToLowerInvariant();
                    if(request.Format==OutputFormat.Compress) {
                        if(ext==".pdf")pdf.Compress(source,target,cancel);
                        else {
                            using(var stream=File.OpenRead(source)){try {var decoder=BitmapDecoder.Create(stream,BitmapCreateOptions.PreservePixelFormat,BitmapCacheOption.OnLoad);if(decoder.Frames.Count>1)throw new SkipFileException("여러 프레임 이미지는 전체 프레임 보존을 위해 건너뜁니다.");}catch(NotSupportedException){}}
                            var bitmap=Images.Load(source).Single();if(request.ProtectText&&request.RetainPercent<100)throw new SkipFileException("글자 보호 설정으로 해상도 축소를 건너뜁니다.");
                            var resized=Images.Resize(bitmap,request.RetainPercent);bool jpeg=ext is ".jpg" or ".jpeg";target=work.File(jpeg?"jpeg":"png");Images.Save(resized,target,jpeg);
                        }
                        long before=new FileInfo(source).Length;if(new FileInfo(target).Length>=before)throw new SkipFileException("원본보다 작아지지 않아 저장하지 않았습니다.");
                        var outputExt=ext==".pdf"?".pdf":Path.GetExtension(target);Publish(source,target,Path.Combine(Path.GetDirectoryName(source)!,Path.GetFileNameWithoutExtension(source)+"_용량축소"+outputExt),before);
                    }else if(request.Format is OutputFormat.Png or OutputFormat.Jpeg) {
                        var pages=Capabilities.IsImage(source)?Pages([source]):pdf.Render(AsPdf(source),work,request.Dpi,cancel);int number=0;
                        foreach(var imagePage in pages){cancel.ThrowIfCancellationRequested();number++;Images.Save(Images.Load(imagePage.ImagePath)[0],target,request.Format==OutputFormat.Jpeg);string stem=Path.GetFileNameWithoutExtension(source)+(pages.Count>1?$"_{number:000}":"");Publish(source,target,Path.Combine(Path.GetDirectoryName(source)!,stem+"."+Capabilities.Extension(request.Format)));}
                    }else {
                        if(request.Format==OutputFormat.Pdf)target=AsPdf(source);
                        else if(request.Format==OutputFormat.Hwpx&&(Capabilities.IsImage(source)||ext==".pdf"))office.ImageDocument(Pages([source]),target,work,ext==".pdf",cancel);
                        else if(request.Format==OutputFormat.Pptx)office.Slides(Pages([source]),target,work,cancel);
                        else office.Export(source,target,request.Format,cancel);
                        Publish(source,target,Path.ChangeExtension(source,Capabilities.Extension(request.Format)));
                    }
                }catch(SkipFileException error){results.Add(new(source,null,FileOutcome.Skipped,0,0,error.Message));}
                catch(Exception error) when(error is not OperationCanceledException){Log(error);results.Add(new(source,null,FileOutcome.Failed,0,0,Friendly(error)));}
            }
        }catch(OperationCanceledException){cancelled=true;}
        catch(Exception error){Log(error);results.Add(new("",null,FileOutcome.Failed,0,0,Friendly(error)));}
        return new(results,cancelled,clock.Elapsed);
    }
    public static void Log(Exception error){try {Directory.CreateDirectory(TrialPaths.Root);File.AppendAllText(Path.Combine(TrialPaths.Root,"errors.log"),$"{DateTimeOffset.Now:O} {error}\n");}catch(IOException){}catch(UnauthorizedAccessException){}}
    public static string Friendly(Exception error)=>error switch {ArgumentException=>error.Message,SkipFileException=>error.Message,UnauthorizedAccessException=>"저장 권한을 확인하고 파일을 닫은 뒤 다시 시도해 주세요.",System.Runtime.InteropServices.COMException=>"한글·Office 설치 상태와 원본 파일을 확인해 주세요.",_=>"작업을 완료하지 못했습니다. 원본 파일이 정상적으로 열리는지 확인해 주세요. 원본은 보존됩니다."};
}
