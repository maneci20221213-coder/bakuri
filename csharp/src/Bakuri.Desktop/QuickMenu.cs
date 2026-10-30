using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using Bakuri.Core;
using Forms=System.Windows.Forms;
namespace Bakuri.Desktop;

public sealed class QuickMenu : Window {
    public QuickMenu(IReadOnlyList<string> paths,Action<OutputFormat,bool> choose) {
        WindowStyle=WindowStyle.None;AllowsTransparency=true;Background=Brushes.Transparent;ShowInTaskbar=false;Topmost=true;ResizeMode=ResizeMode.NoResize;Width=326;Height=244;
        var grid=new Grid();for(int i=0;i<3;i++){grid.RowDefinitions.Add(new RowDefinition());grid.ColumnDefinitions.Add(new ColumnDefinition());}Content=grid;
        void Add(string label,int row,int column,OutputFormat format,bool expand=false) {
            var button=new Button{Content=label,Margin=new Thickness(4),Background=new SolidColorBrush(Color.FromArgb(240,255,255,255)),IsEnabled=expand||paths.All(p=>Capabilities.Supports(p,format))};
            button.Click+=(_,_)=>{Hide();choose(format,expand);};Grid.SetRow(button,row);Grid.SetColumn(button,column);grid.Children.Add(button);
        }
        bool pdfs=paths.All(p=>Path.GetExtension(p).Equals(".pdf",StringComparison.OrdinalIgnoreCase));
        Add(pdfs?"PDF 합치기":"PDF",0,1,OutputFormat.Pdf);Add(paths.All(p=>Path.GetExtension(p).Equals(".png",StringComparison.OrdinalIgnoreCase))?"JPEG":"PNG",1,0,paths.All(p=>Path.GetExtension(p).Equals(".png",StringComparison.OrdinalIgnoreCase))?OutputFormat.Jpeg:OutputFormat.Png);
        Add("한글",1,2,OutputFormat.Hwpx);Add("용량 축소",1,1,OutputFormat.Compress);Add("확장 기능",2,1,OutputFormat.Pdf,true);
        Deactivated+=(_,_)=>Hide();PreviewKeyDown+=(_,e)=>{if(e.Key==Key.Escape){Hide();e.Handled=true;}};
    }
    public void ShowAtCursor() {
        var cursor=Forms.Cursor.Position;var source=PresentationSource.FromVisual(System.Windows.Application.Current.MainWindow);var point=source?.CompositionTarget.TransformFromDevice.Transform(new Point(cursor.X,cursor.Y))??new Point(cursor.X,cursor.Y);var area=SystemParameters.WorkArea;
        Left=Math.Clamp(point.X-Width/2,area.Left,Math.Max(area.Left,area.Right-Width));Top=Math.Clamp(point.Y-Height/2,area.Top,Math.Max(area.Top,area.Bottom-Height));Opacity=0;Show();BeginAnimation(OpacityProperty,new DoubleAnimation(0,1,TimeSpan.FromMilliseconds(140)){EasingFunction=new CubicEase{EasingMode=EasingMode.EaseOut}});Activate();
    }
}
