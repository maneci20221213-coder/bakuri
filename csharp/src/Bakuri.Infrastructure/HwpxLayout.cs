using System.IO.Compression;
using System.Xml.Linq;
namespace Bakuri.Infrastructure;

public static class HwpxLayout
{
    static readonly XNamespace Hp = "http://www.hancom.co.kr/hwpml/2011/paragraph";
    static Dictionary<string, byte[]> Read(string path)
    {
        using var zip = ZipFile.OpenRead(path);
        return zip.Entries.Where(e => e.FullName.EndsWith(".xml") || e.FullName.EndsWith(".hpf")).ToDictionary(e => e.FullName, e => { using var stream = e.Open(); using var memory = new MemoryStream(); stream.CopyTo(memory); return memory.ToArray(); });
    }
    static byte[] Xml(XDocument document)
    {
        using var stream = new MemoryStream();
        document.Save(stream);
        return stream.ToArray();
    }
    static XDocument Parse(byte[] data)
    {
        using var stream = new MemoryStream(data);
        return XDocument.Load(stream);
    }
    static void Attributes(XElement element, params (string Key, object Value)[] pairs)
    {
        foreach (var (key, value) in pairs)
            element.SetAttributeValue(key, value);
    }
    static XElement Child(XElement parent, string name)
    {
        var child = parent.Element(Hp + name);
        if (child == null)
        {
            child = new XElement(Hp + name);
            parent.Add(child);
        }
        return child;
    }
    static void Write(string path, Dictionary<string, byte[]> replacements, IReadOnlySet<string>? removed = null)
    {
        string temp = path + ".repack";
        try
        {
            using (var source = ZipFile.OpenRead(path))
            using (var zip = ZipFile.Open(temp, ZipArchiveMode.Create))
            {
                foreach (var original in source.Entries.OrderBy(e => e.FullName == "mimetype" ? 0 : 1))
                {
                    if (replacements.ContainsKey(original.FullName) || removed?.Contains(original.FullName) == true)
                        continue;
                    var entry = zip.CreateEntry(original.FullName, original.FullName == "mimetype" ? CompressionLevel.NoCompression : CompressionLevel.SmallestSize);
                    using var input = original.Open();
                    using var output = entry.Open();
                    input.CopyTo(output, 81920);
                }
                foreach (var (name, data) in replacements)
                {
                    var entry = zip.CreateEntry(name, CompressionLevel.SmallestSize);
                    using var stream = entry.Open();
                    stream.Write(data);
                }
            }
            File.Move(temp, path, true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    public static void Repack(string path) => Write(path, new());
    public static void Paginate(string path, IReadOnlyList<ImagePage> pages)
    {
        var files = Read(path);
        var names = files.Keys.Where(n => n.StartsWith("Contents/section") && n.EndsWith(".xml")).ToArray();
        if (names.Length != 1)
            throw new IOException("PDF 페이지 배치용 기본 구역이 올바르지 않습니다.");
        var template = Parse(files[names[0]]);
        var table = template.Descendants(Hp + "tbl").Single();
        var rows = table.Elements(Hp + "tr").ToArray();
        if (rows.Length != pages.Count)
            throw new IOException("PDF 페이지 수와 그림 수가 다릅니다.");
        var content = Parse(files["Contents/content.hpf"]);
        XNamespace opf = content.Root!.Name.Namespace;
        var manifest = content.Root.Element(opf + "manifest") ?? throw new IOException("문서 구역 목록이 없습니다.");
        var spine = content.Root.Element(opf + "spine") ?? throw new IOException("문서 구역 순서가 없습니다.");
        var oldIds = manifest.Elements().Where(e => names.Contains((string?)e.Attribute("href")) || ((string?)e.Attribute("href"))?.StartsWith("section") == true).Select(e => (string?)e.Attribute("id")).ToHashSet();
        manifest.Elements().Where(e => oldIds.Contains((string?)e.Attribute("id"))).Remove();
        spine.Elements().Where(e => oldIds.Contains((string?)e.Attribute("idref"))).Remove();
        foreach (var name in names)
            files.Remove(name);
        for (int i = 0; i < pages.Count; i++)
        {
            int width = checked((int)Math.Round(pages[i].WidthPoints * 100)), height = checked((int)Math.Round(pages[i].HeightPoints * 100));
            var section = new XDocument(template);
            var oldTable = section.Descendants(Hp + "tbl").Single();
            var picture = new XElement(rows[i].Descendants(Hp + "pic").Single());
            Attributes(picture, ("id", 100000 + i), ("textWrap", "IN_FRONT_OF_TEXT"), ("textFlow", "BOTH_SIDES"));
            Attributes(Child(picture, "sz"), ("width", width), ("height", height), ("widthRelTo", "ABSOLUTE"), ("heightRelTo", "ABSOLUTE"), ("protect", 0));
            Attributes(Child(picture, "pos"), ("treatAsChar", 0), ("affectLSpacing", 0), ("flowWithText", 0), ("allowOverlap", 1), ("holdAnchorAndSO", 1), ("vertRelTo", "PAPER"), ("horzRelTo", "PAPER"), ("vertAlign", "TOP"), ("horzAlign", "LEFT"), ("vertOffset", 0), ("horzOffset", 0));
            foreach (var marginName in new[] { "outMargin", "inMargin" })
            if (picture.Element(Hp + marginName) is { } margin)
                Attributes(margin, ("left", 0), ("right", 0), ("top", 0), ("bottom", 0));
            if (picture.Element(Hp + "curSz") is { } size)
                Attributes(size, ("width", width), ("height", height));
            if (picture.Element(Hp + "offset") is { } offset)
                Attributes(offset, ("x", 0), ("y", 0));
            var original = picture.Element(Hp + "orgSz");
            double ow = (double?)original?.Attribute("width") ?? width, oh = (double?)original?.Attribute("height") ?? height;
            if (ow <= 0 || oh <= 0)
                throw new IOException("PDF 그림의 원래 크기가 올바르지 않습니다.");
            if (picture.Element(Hp + "renderingInfo") is { } rendering)
            foreach (var matrix in rendering.Elements())
            if (new[] { "transMatrix", "scaMatrix", "rotMatrix" }.Contains(matrix.Name.LocalName))
                Attributes(matrix, ("e1", matrix.Name.LocalName == "scaMatrix" ? width / ow : 1), ("e2", 0), ("e3", 0), ("e4", 0), ("e5", matrix.Name.LocalName == "scaMatrix" ? height / oh : 1), ("e6", 0));
            if (picture.Element(Hp + "rotationInfo") is { } rotation)
                rotation.SetAttributeValue("angle", 0);
            if (picture.Element(Hp + "lineShape") is { } line)
                Attributes(line, ("style", "NONE"), ("width", 0));
            var anchor = oldTable.Ancestors().First(e => e.Parent == section.Root);
            oldTable.ReplaceWith(picture);
            section.Root!.Elements().Where(e => e != anchor).Remove();
            section.Descendants(Hp + "linesegarray").Remove();
            var page = section.Descendants(Hp + "pagePr").First();
            Attributes(page, ("width", Math.Min(width, height)), ("height", Math.Max(width, height)), ("landscape", width > height ? "NARROWLY" : "WIDELY"));
            foreach (var key in new[] { "left", "right", "top", "bottom", "header", "footer", "gutter" })
                Child(page, "margin").SetAttributeValue(key, 0);
            section.Root.SetAttributeValue("id", i);
            string name = $"Contents/section{i}.xml";
            files[name] = Xml(section);
            manifest.Add(new XElement(opf + "item", new XAttribute("id", $"section{i}"), new XAttribute("href", name), new XAttribute("media-type", "application/xml")));
            spine.Add(new XElement(opf + "itemref", new XAttribute("idref", $"section{i}"), new XAttribute("linear", "yes")));
        }
        files["Contents/content.hpf"] = Xml(content);
        var header = Parse(files["Contents/header.xml"]);
        header.Root!.SetAttributeValue("secCnt", pages.Count);
        files["Contents/header.xml"] = Xml(header);
        Write(path, files, names.ToHashSet());
    }
}
