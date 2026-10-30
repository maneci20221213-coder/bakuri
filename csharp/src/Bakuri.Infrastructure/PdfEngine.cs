using Bakuri.Core;
using MuPDF.NET;
namespace Bakuri.Infrastructure;

/// <summary>The only module aware of the MuPDF.NET API. Replaceable without changing the UI or job records.</summary>
public sealed class PdfEngine
{
    static Document Open(string path)
    {
        var document = new Document(path);
        if (document.NeedsPass)
        {
            document.Dispose();
            throw new IOException("암호가 있는 PDF는 지원하지 않습니다.");
        }
        return document;
    }
    public void Merge(IReadOnlyList<string> paths, string target, CancellationToken cancel)
    {
        using var merged = new Document();
        foreach (var path in paths)
        {
            cancel.ThrowIfCancellationRequested();
            using var part = Open(path);
            merged.InsertPdf(part);
        }
        cancel.ThrowIfCancellationRequested();
        Save(merged, target);
    }
    public void FromImages(string path, string target, WorkDirectory work, CancellationToken cancel)
    {
        using var pdf = new Document();
        if (Images.OriginalGeometry(path) is { } geometry)
        {
            cancel.ThrowIfCancellationRequested();
            var page = pdf.NewPage(width: (float)(geometry.Width * 72d / 150), height: (float)(geometry.Height * 72d / 150));
            page.InsertImage(page.Rect, filename: path);
            Save(pdf, target);
            return;
        }
        var frames = Images.Load(path);
        foreach (var frame in frames)
        {
            cancel.ThrowIfCancellationRequested();
            var page = pdf.NewPage(width: (float)(frame.PixelWidth * 72d / 150), height: (float)(frame.PixelHeight * 72d / 150));
            // WIC normalizes orientation; PNG stays lossless, and original JPEG streams avoid recompression.
            bool originalJpeg = Images.CanEmbedOriginal(path);
            page.InsertImage(page.Rect, filename: originalJpeg ? path : Images.Stage(frame, work));
        }
        Save(pdf, target);
    }
    public IReadOnlyList<ImagePage> Render(string path, WorkDirectory work, int dpi, CancellationToken cancel)
    {
        var pages = new List<ImagePage>();
        using var document = Open(path);
        for (int i = 0; i < document.PageCount; i++)
        {
            cancel.ThrowIfCancellationRequested();
            var page = document[i];
            using var pixmap = page.GetPixmap(dpi: dpi, alpha: false);
            var image = work.File("png");
            pixmap.Save(image);
            pages.Add(new(image, page.Rect.Width, page.Rect.Height));
        }
        return pages;
    }
    public int PageCount(string path)
    {
        using var document = Open(path);
        return document.PageCount;
    }
    public void Compress(string path, string target, CancellationToken cancel)
    {
        using var document = Open(path);
        if (document.GetSigFlags() > 0)
            throw new SkipFileException("서명이 있는 PDF는 건너뜁니다.");
        cancel.ThrowIfCancellationRequested();
        Save(document, target);
    }
    public static void Save(Document document, string target) => document.Save(target, garbage: 4, deflate: 1, deflateImages: 1, deflateFonts: 1);
}
public sealed class SkipFileException(string message) : Exception(message);
