using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

internal sealed class Launcher : Form {
    readonly string root = AppDomain.CurrentDomain.BaseDirectory;
    readonly TextBox output = new TextBox();
    readonly Label status = new Label();
    readonly Button setup = new Button(), download = new Button(), launch = new Button(), check = new Button();
    bool busy;
    public Launcher() {
        Text = "Sikander's Trellis 2"; ClientSize = new Size(810, 590);
        MinimumSize = new Size(830, 620); StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(17,17,19); ForeColor = Color.White;
        Font = new Font("Segoe UI", 10);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(26), ColumnCount = 1, RowCount = 6 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,52));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,48));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,60));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,48));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,35));
        layout.Controls.Add(new Label { Text="SIKANDER'S TRELLIS 2", Font=new Font("Segoe UI",22,FontStyle.Bold), ForeColor=Color.FromArgb(255,120,45), Dock=DockStyle.Fill },0,0);
        layout.Controls.Add(new Label { Text="Your local 3D studio. Set up once, then launch whenever inspiration strikes.\nFirst setup downloads both engines. Allow at least 60 GB of free space.", Dock=DockStyle.Fill },0,1);
        var buttons = new FlowLayoutPanel { Dock=DockStyle.Fill, WrapContents=false };
        AddButton(buttons,setup,"Setup & download","setup",190);
        AddButton(buttons,download,"Download models","download",180);
        AddButton(buttons,launch,"Launch studio", "launch",165);
        AddButton(buttons,check,"Check", "check",90);
        layout.Controls.Add(buttons,0,2);
        status.Dock=DockStyle.Fill; layout.Controls.Add(status,0,3);
        output.Multiline=true; output.ReadOnly=true; output.ScrollBars=ScrollBars.Vertical;
        output.BackColor=Color.FromArgb(26,26,29); output.ForeColor=Color.Gainsboro;
        output.Font=new Font("Consolas",9); output.Dock=DockStyle.Fill; output.BorderStyle=BorderStyle.FixedSingle;
        layout.Controls.Add(output,0,4);
        var logs = new LinkLabel { Text="Open logs folder", Dock=DockStyle.Fill, LinkColor=Color.FromArgb(255,150,80), Padding=new Padding(0,8,0,0) };
        logs.LinkClicked += delegate { Directory.CreateDirectory(Path.Combine(root,"logs")); Process.Start("explorer.exe",Quote(Path.Combine(root,"logs"))); };
        var links=new FlowLayoutPanel { Dock=DockStyle.Fill };
        logs.AutoSize=true; logs.Dock=DockStyle.None;
        links.Controls.Add(logs);
        var stop=new LinkLabel { Text="Stop studio", AutoSize=true, LinkColor=Color.FromArgb(255,150,80), Padding=new Padding(20,8,0,0) };
        stop.LinkClicked += async delegate { if(!busy) await RunAction("stop"); };
        links.Controls.Add(stop); layout.Controls.Add(links,0,5); Controls.Add(layout);
        RefreshState();
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if(busy) { e.Cancel=true; WindowState=FormWindowState.Minimized; } };
    }
    static string Quote(string s) { return "\""+s+"\""; }
    void AddButton(FlowLayoutPanel panel, Button button, string text, string action, int width) {
        button.Text=text; button.UseMnemonic=false; button.Size=new Size(width,44); button.FlatStyle=FlatStyle.Flat;
        button.BackColor=Color.FromArgb(255,120,45); button.ForeColor=Color.Black;
        button.FlatAppearance.BorderSize=0; button.Cursor=Cursors.Hand;
        button.Click += async delegate { await RunAction(action); }; panel.Controls.Add(button);
    }
    void RefreshState() {
        bool installed=File.Exists(Path.Combine(root,".venv/Scripts/python.exe"));
        setup.Enabled=!busy; download.Enabled=!busy && installed; launch.Enabled=!busy && installed; check.Enabled=!busy && installed;
        if(!busy) status.Text=installed ? "Environment found. Download models if needed, or launch the studio." : "Start with Setup & download. Interrupted downloads can be retried.";
    }
    void Append(string line) {
        if(line==null || IsDisposed) return;
        BeginInvoke((Action)delegate { if(output.TextLength>180000) output.Text=output.Text.Substring(output.TextLength-90000); output.AppendText(line+Environment.NewLine); });
    }
    async Task RunAction(string action) {
        busy=true; RefreshState(); status.Text="Working. Progress appears below. Closing this window minimizes it until this step finishes.";
        output.Clear();
        try {
            int result=await Task.Run(()=> {
                var info=new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"WindowsPowerShell/v1.0/powershell.exe"),
                    "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "+Quote(Path.Combine(root,"scripts/launcher.ps1"))+" -Action "+action);
                info.WorkingDirectory=root; info.UseShellExecute=false; info.CreateNoWindow=true;
                info.RedirectStandardOutput=true; info.RedirectStandardError=true;
                info.EnvironmentVariables["PYTHONUTF8"]="1"; info.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
                using(var process=new Process { StartInfo=info }) {
                    process.OutputDataReceived += (s,e)=>Append(e.Data); process.ErrorDataReceived += (s,e)=>Append(e.Data);
                    process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit(); return process.ExitCode;
                }
            });
            busy=false; RefreshState(); status.Text=result==0 ? (action=="launch" ? "Studio opened in your browser. It keeps running when you close this launcher." : "Finished. You can now launch the studio.") : "This step stopped. Review the log below, then retry.";
        } catch(Exception ex) { busy=false; RefreshState(); status.Text="Could not start: "+ex.Message; }
    }
    [STAThread] static int Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        using(var form=new Launcher()) {
            if(args.Length==1 && args[0]=="--self-test") {
                bool valid=File.Exists(Path.Combine(form.root,"scripts/launcher.ps1")) && form.setup.Enabled && form.Controls.Count==1;
                Directory.CreateDirectory(Path.Combine(form.root,"logs"));
                form.StartPosition=FormStartPosition.Manual; form.Location=new Point(-10000,-10000);
                form.Show(); Application.DoEvents(); form.PerformLayout();
                using(var bitmap=new Bitmap(form.Width,form.Height)) {
                    form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));
                    bitmap.Save(Path.Combine(form.root,"logs/launcher-preview.png"));
                }
                File.WriteAllText(Path.Combine(form.root,"logs/launcher-self-test.txt"),valid ? "PASS" : "FAIL"); return valid?0:1;
            }
            Application.Run(form);
        }
        return 0;
    }
}
