using System.ComponentModel;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Bakuri.Core;
using Bakuri.Infrastructure;
using Forms=System.Windows.Forms;
namespace Bakuri.Desktop;

public partial class MainWindow : Window {
    readonly MainViewModel vm;readonly Forms.NotifyIcon tray;readonly bool smoke;
    TrialSettings settings=TrialSettings.Load();QuickMenu? popup;GlobalHotkey? hotkey;bool exiting;bool optionsValid=true;bool querying;double oldWidth=900;
    public MainWindow(bool uiSmoke=false) {
        smoke=uiSmoke;InitializeComponent();vm=new(new ConversionService(new StaRunner()),new FileStore(),new JsonRenameJournal(Path.Combine(TrialPaths.Root,"rename-history.json")));DataContext=vm;
        Icon=System.Windows.Media.Imaging.BitmapFrame.Create(new Uri(Path.Combine(AppContext.BaseDirectory,"app.ico")));
        tray=new Forms.NotifyIcon{Icon=new System.Drawing.Icon(Path.Combine(AppContext.BaseDirectory,"app.ico")),Text="바꾸리 C# 시험판",Visible=!smoke};
        var menu=new Forms.ContextMenuStrip();menu.Items.Add("열기",null,(_,_)=>Dispatcher.Invoke(Open));menu.Items.Add("최근 결과 보기",null,(_,_)=>Dispatcher.Invoke(ShowResults));menu.Items.Add("작업 중지",null,(_,_)=>Dispatcher.Invoke(vm.Stop));menu.Items.Add("완전 종료",null,(_,_)=>Dispatcher.Invoke(()=>{if(vm.Busy){exiting=true;vm.Stop();}else Exit();}));tray.ContextMenuStrip=menu;tray.DoubleClick+=(_,_)=>Dispatcher.Invoke(Open);
        vm.CapabilitiesChanged+=()=>FormatChanged(this,new SelectionChangedEventArgs(SelectorEvent,Array.Empty<object>(),Array.Empty<object>()));
        vm.Completed+=text=>{if(settings.Notify)tray.ShowBalloonTip(7000,"바꾸리 C# 시험판",text,Forms.ToolTipIcon.Info);if(exiting)Exit();};
        vm.PropertyChanged+=(_,e)=>{if(e.PropertyName==nameof(vm.Status))tray.Text=("바꾸리 C# · "+vm.Status)[..Math.Min(63,("바꾸리 C# · "+vm.Status).Length)];if(e.PropertyName==nameof(vm.Busy))RunButton.Content=vm.Busy?"작업 중지":Tabs.SelectedIndex==1?"이름 변경 적용":"변환 시작 →";};
        Loaded+=(_,_)=>{if(!smoke){hotkey=new GlobalHotkey(this,TogglePopup);try{hotkey.Register(settings.Hotkey);}catch(Exception error){vm.Status=error.Message;}}else{Tabs.SelectedIndex=1;CommonText.Text="시험_";}OptionsChanged(this,new RoutedEventArgs());};
        Closing+=OnClosing;
    }
    public void AddPaths(IEnumerable<string> paths){vm.Add(paths);FormatChanged(this,new SelectionChangedEventArgs(SelectorEvent,Array.Empty<object>(),Array.Empty<object>()));}
    static readonly RoutedEvent SelectorEvent=System.Windows.Controls.Primitives.Selector.SelectionChangedEvent;
    void ChooseFiles(object sender,RoutedEventArgs e){var dialog=new Microsoft.Win32.OpenFileDialog{Multiselect=true,Filter="모든 파일|*.*"};if(dialog.ShowDialog(this)==true)AddPaths(dialog.FileNames);}
    void SortFiles(object sender,RoutedEventArgs e)=>vm.Sort();void RemoveFiles(object sender,RoutedEventArgs e)=>vm.RemoveChecked();
    void CheckAll(object sender,RoutedEventArgs e){if(!IsInitialized||DataContext==null)return;foreach(var row in vm.Files)row.Selected=((CheckBox)sender).IsChecked==true;}
    void FilesDropped(object sender,DragEventArgs e){if(e.Data.GetDataPresent(DataFormats.FileDrop))AddPaths((string[])e.Data.GetData(DataFormats.FileDrop));}
    void WindowKeyDown(object sender,KeyEventArgs e){if(e.Key==Key.F1){HelpClick(sender,e);e.Handled=true;}if(e.Key==Key.V&&Keyboard.Modifiers.HasFlag(ModifierKeys.Control)&&Keyboard.FocusedElement is not TextBox&&Clipboard.ContainsFileDropList()){AddPaths(Clipboard.GetFileDropList().Cast<string>());e.Handled=true;}}
    void GridKeyDown(object sender,KeyEventArgs e) {
        if(vm.Busy)return;if(e.Key==Key.Delete&&Keyboard.FocusedElement is not TextBox){vm.RemoveChecked();e.Handled=true;return;}
        if(e.Key!=Key.V||!Keyboard.Modifiers.HasFlag(ModifierKeys.Control)||!Clipboard.ContainsText()||Clipboard.ContainsFileDropList()||Tabs.SelectedIndex!=1)return;
        var column=FileGrid.CurrentCell.Column;if(column!=ExtraColumn&&column!=NextColumn)return;string text=Clipboard.GetText();if(Keyboard.FocusedElement is TextBox&&!text.Contains('\n')&&!text.Contains('\r')&&!text.Contains('\t'))return;
        try {
            int start=FileGrid.CurrentItem is FileRow current?vm.Files.IndexOf(current):0;var rows=vm.Files.Skip(Math.Max(0,start)).Where(f=>f.Selected).ToArray();var values=column==ExtraColumn?Names.FillDown(text,rows.Length):Names.Lines(text);
            if(values.Length>rows.Length)throw new ArgumentException("붙여넣을 줄 수가 남은 체크 파일 수보다 많습니다.");
            FileGrid.CancelEdit();for(int i=0;i<values.Length;i++)if(column==ExtraColumn)rows[i].Extra=values[i];else rows[i].NextName=values[i];vm.Refresh();
        }catch(ArgumentException error){vm.Status=error.Message;}e.Handled=true;
    }
    void CellEdited(object sender,DataGridCellEditEndingEventArgs e)=>Dispatcher.BeginInvoke(new Action(vm.QueuePreview));
    void ModeChanged(object sender,SelectionChangedEventArgs e) {
        if(!IsInitialized||DataContext==null)return;bool rename=Tabs.SelectedIndex==1;
        if(rename){oldWidth=Width;MinWidth=1100;Width=Math.Max(Width,1100);}else{MinWidth=800;if(WindowState!=WindowState.Maximized)Width=oldWidth;}
        RenameOptionsPanel.Visibility=rename?Visibility.Visible:Visibility.Collapsed;ConversionOptions.Visibility=rename?Visibility.Collapsed:Visibility.Visible;NextColumn.Visibility=StateColumn.Visibility=UndoButton.Visibility=rename?Visibility.Visible:Visibility.Collapsed;SizeColumn.Visibility=rename?Visibility.Collapsed:Visibility.Visible;RunButton.Content=rename?"이름 변경 적용":"변환 시작 →";OptionsChanged(sender,e);
    }
    void BaseChanged(object sender,TextChangedEventArgs e){if(IsInitialized&&NumberEnabled!=null&&BaseName.Text.Length>0)NumberEnabled.IsChecked=true;OptionsChanged(sender,e);}
    void OptionsChanged(object sender,RoutedEventArgs e) {
        if(!IsInitialized||DataContext==null)return;bool perFile=PerFile.IsChecked==true;CommonText.IsEnabled=!perFile;ExtraColumn.Visibility=perFile&&Tabs.SelectedIndex==1?Visibility.Visible:Visibility.Collapsed;
        TextMarker.Visibility=TextPosition.SelectedIndex>=2?Visibility.Visible:Visibility.Collapsed;NumberMarker.Visibility=NumberPosition.SelectedIndex>=2?Visibility.Visible:Visibility.Collapsed;
        if(!int.TryParse(Start.Text,out int start)||start<0||!int.TryParse(Digits.Text,out int digits)||digits<1||digits>8){optionsValid=false;vm.Status="시작 번호는 0 이상, 자릿수는 1~8로 입력해 주세요.";return;}
        optionsValid=true;vm.Configure(new(Find.Text,Replace.Text,BaseName.Text,CommonText.Text,(InsertPosition)TextPosition.SelectedIndex,TextMarker.Text,perFile,NumberEnabled.IsChecked==true,start,digits,(string)((ComboBoxItem)Separator.SelectedItem).Tag,(InsertPosition)NumberPosition.SelectedIndex,NumberMarker.Text));
    }
    void FormatChanged(object sender,SelectionChangedEventArgs e) {
        if(!IsInitialized||DataContext==null)return;if(Format.SelectedItem is not FormatChoice choice||!choice.Enabled){Format.SelectedItem=vm.Formats.FirstOrDefault(f=>f.Enabled);return;}
        Merge.IsEnabled=Capabilities.CanMerge(vm.Files.Where(f=>f.Selected).Select(f=>f.FullPath),choice.Value);if(!Merge.IsEnabled)Merge.IsChecked=false;
        Ratio.IsEnabled=choice.Value==OutputFormat.Compress;Protect.IsEnabled=choice.Value==OutputFormat.Compress;
    }
    void RatioChanged(object sender,SelectionChangedEventArgs e){if(IsInitialized&&DataContext!=null)settings=settings with{RetainPercent=int.Parse((string)((ComboBoxItem)Ratio.SelectedItem).Tag)};}
    async void RunClick(object sender,RoutedEventArgs e){FileGrid.CommitEdit(DataGridEditingUnit.Cell,true);FileGrid.CommitEdit(DataGridEditingUnit.Row,true);if(vm.Busy){vm.Stop();return;}if(Tabs.SelectedIndex==1){if(!optionsValid){vm.Status="시작 번호와 자릿수를 확인해 주세요.";return;}await vm.Rename(false);}else if(Format.SelectedItem is FormatChoice choice)await vm.Convert(choice.Value,Merge.IsChecked==true,settings,Protect.IsChecked==true);}
    async void UndoClick(object sender,RoutedEventArgs e)=>await vm.Rename(true);
    void Open(){Show();if(WindowState==WindowState.Minimized)WindowState=WindowState.Normal;Activate();}
    void OnClosing(object? sender,CancelEventArgs e){if(exiting&&!vm.Busy)return;e.Cancel=true;vm.Clear();Hide();}
    void Exit(){hotkey?.Dispose();popup?.Close();tray.Dispose();exiting=true;System.Windows.Application.Current.Shutdown();}
    void ShowResults(){var report=vm.LastReport;string text=report==null?vm.Status:report.Summary+"\n\n"+string.Join("\n",report.Files.Select(f=>$"{Path.GetFileName(f.Source)} → {f.Message}"));MessageBox.Show(text,"최근 작업 결과");}
    void HelpClick(object sender,RoutedEventArgs e)=>MessageBox.Show("파일 추가 → 출력 형식 선택 → 변환 시작\n파일명 변경 탭에서 미리보기 확인 후 적용\n엑셀 한 열·메모장 여러 줄을 추가할 문자열/변경될 이름 열에 Ctrl+V\n완료 결과는 트레이 우클릭 → 최근 결과 보기\n\n간편메뉴: 탐색기에서 파일 선택 후 "+settings.Hotkey+"\nPDF는 픽셀을 유지하는 압축만 지원합니다.\n한글·Office 변환에는 해당 프로그램이 필요합니다.\n이 시험판은 자동 업데이트·자동 실행·우클릭 메뉴를 등록하지 않습니다.","C# 시험판 사용 설명");
    void SettingsClick(object sender,RoutedEventArgs e) {
        if(vm.Busy)return;var dialog=new Window{Title="C# 시험판 설정",Owner=this,Width=390,Height=270,ResizeMode=ResizeMode.NoResize,WindowStartupLocation=WindowStartupLocation.CenterOwner};var panel=new StackPanel{Margin=new Thickness(18)};
        panel.Children.Add(new TextBlock{Text="정식판과 단축키가 겹치지 않게 선택하세요.",Margin=new Thickness(4)});var keys=new ComboBox{ItemsSource=new[]{"Ctrl+Alt+F9","F9","F8","Ctrl+Alt+B"},SelectedItem=settings.Hotkey};panel.Children.Add(keys);var notify=new CheckBox{Content="완료 알림",IsChecked=settings.Notify};panel.Children.Add(notify);var save=new Button{Content="저장"};panel.Children.Add(save);save.Click+=(_,_)=>{try{hotkey?.Register((string)keys.SelectedItem);settings=settings with{Hotkey=(string)keys.SelectedItem,Notify=notify.IsChecked==true};settings.Save();dialog.Close();}catch(Exception error){MessageBox.Show(error.Message,"단축키 설정");}};dialog.Content=panel;dialog.ShowDialog();
    }
    async void TogglePopup() {
        if(popup?.IsVisible==true){popup.Hide();return;}if(vm.Busy||querying)return;querying=true;
        try {
            var paths=await ExplorerSelection.ReadAsync();if(paths.Count==0){vm.Status="탐색기에서 파일을 선택한 뒤 단축키를 눌러 주세요.";return;}
            popup?.Close();popup=new QuickMenu(paths,async(format,expand)=>{if(expand){AddPaths(paths);Open();return;}vm.Clear();AddPaths(paths);await vm.Convert(format,paths.Count>1&&Capabilities.CanMerge(paths,format),settings,false);});popup.ShowAtCursor();
        }catch(Exception error){vm.Status=ConversionService.Friendly(error);}finally{querying=false;}
    }
}
