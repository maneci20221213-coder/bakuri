using System.Windows;
using Bakuri.Infrastructure;
namespace Bakuri.Desktop;
public partial class App : Application {
    Mutex? instance;
    protected override void OnStartup(StartupEventArgs e) {
        base.OnStartup(e);DispatcherUnhandledException+=(_,args)=>{ConversionService.Log(args.Exception);MessageBox.Show(ConversionService.Friendly(args.Exception),"바꾸리 C# 시험판");args.Handled=true;};
        instance=new Mutex(true,@"Local\BakuriCSharpTrial",out bool created);
        if(!created){MessageBox.Show("C# 시험판이 이미 실행 중입니다. 트레이 아이콘에서 열어 주세요.");Shutdown();return;}
        var window=new MainWindow(e.Args.Contains("--ui-smoke"));MainWindow=window;window.Show();
        if(e.Args.Contains("--ui-smoke"))window.AddPaths(e.Args.Skip(1).Where(Directory.Exists).SelectMany(Directory.EnumerateFiles));
    }
    protected override void OnExit(ExitEventArgs e){instance?.Dispose();base.OnExit(e);}
}
