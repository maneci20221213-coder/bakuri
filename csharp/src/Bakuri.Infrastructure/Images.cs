using System.Windows.Media;
using System.Windows.Media.Imaging;
using SkiaSharp;
namespace Bakuri.Infrastructure;

public sealed record ImagePage(string ImagePath, double WidthPoints, double HeightPoints);
public static class Images
{
    public static IReadOnlyList<BitmapSource> Load(string path)
    {
        try
        {
            using var stream = File.OpenRead(path);
            var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
            var frames = decoder.Frames;
            int count = Path.GetExtension(path).ToLowerInvariant() is ".tif" or ".tiff" ? frames.Count : 1;
            return frames.Take(count).Select(frame => Orient(frame)).ToArray();
        }
        catch (Exception error) when (error is NotSupportedException or FileFormatException)
        {
            using var bitmap = SKBitmap.Decode(path) ?? throw new IOException("이미지를 열 수 없습니다.");
            using var data = bitmap.Encode(SKEncodedImageFormat.Png, 100);
            using var memory = new MemoryStream(data.ToArray());
            var image = BitmapFrame.Create(memory, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.OnLoad);
            image.Freeze();
            return [image];
        }
    }
    static BitmapSource Orient(BitmapFrame frame)
    {
        if ((long)frame.PixelWidth * frame.PixelHeight > 100_000_000)
            throw new IOException("너무 큰 이미지입니다. 페이지나 크기를 줄여 다시 시도해 주세요.");
        ushort orientation = 1;
        try
        {
            if (frame.Metadata is BitmapMetadata metadata && metadata.GetQuery("/app1/ifd/{ushort=274}") is ushort value)
                orientation = value;
        }
        catch (NotSupportedException) { }
        var transforms = new TransformGroup();
        if (orientation is 2 or 4 or 5 or 7)
            transforms.Children.Add(new ScaleTransform(-1, 1));
        int rotation = orientation switch
        {
            3 or 4 => 180,
            5 or 6 => 90,
            7 or 8 => 270,
            _ => 0
        };
        if (rotation != 0)
            transforms.Children.Add(new RotateTransform(rotation));
        BitmapSource result = transforms.Children.Count > 0 ? new TransformedBitmap(frame, transforms) : frame;
        result.Freeze();
        return result;
    }
    public static bool CanEmbedOriginal(string path)
    {
        if (Path.GetExtension(path).Equals(".png", StringComparison.OrdinalIgnoreCase))
            return true;
        if (!(Path.GetExtension(path).ToLowerInvariant() is ".jpg" or ".jpeg"))
            return false;
        using var stream = File.OpenRead(path);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.PreservePixelFormat, BitmapCacheOption.None);
        try
        {
            return decoder.Frames[0].Metadata is not BitmapMetadata metadata || metadata.GetQuery("/app1/ifd/{ushort=274}") is not ushort orientation || orientation == 1;
        }
        catch (NotSupportedException) { return false; }
    }
    public static (int Width, int Height)? OriginalGeometry(string path)
    {
        if (!CanEmbedOriginal(path))
            return null;
        using var stream = File.OpenRead(path);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.DelayCreation, BitmapCacheOption.None);
        int width = decoder.Frames[0].PixelWidth, height = decoder.Frames[0].PixelHeight;
        if ((long)width * height > 100_000_000)
            throw new IOException("너무 큰 이미지입니다. 크기를 줄여 다시 시도해 주세요.");
        return (width, height);
    }
    public static BitmapSource Resize(BitmapSource source, int percent)
    {
        if (percent == 100)
            return source;
        var ratio = Math.Clamp(percent, 10, 100) / 100d;
        var result = new TransformedBitmap(source, new ScaleTransform(ratio, ratio));
        result.Freeze();
        return result;
    }
    public static void Save(BitmapSource bitmap, string target, bool jpeg = false)
    {
        BitmapSource output = bitmap;
        if (jpeg)
        {
            var visual = new DrawingVisual();
            using (var dc = visual.RenderOpen())
            {
                dc.DrawRectangle(Brushes.White, null, new System.Windows.Rect(0, 0, bitmap.PixelWidth, bitmap.PixelHeight));
                dc.DrawImage(bitmap, new System.Windows.Rect(0, 0, bitmap.PixelWidth, bitmap.PixelHeight));
            }
            var rgb = new RenderTargetBitmap(bitmap.PixelWidth, bitmap.PixelHeight, 96, 96, PixelFormats.Pbgra32);
            rgb.Render(visual);
            output = rgb;
        }
        BitmapEncoder encoder = jpeg ? new JpegBitmapEncoder { QualityLevel = 95 } : new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(output));
        using var file = File.Create(target);
        encoder.Save(file);
    }
    public static string Stage(BitmapSource bitmap, WorkDirectory work)
    {
        var path = work.File("png");
        Save(bitmap, path);
        return path;
    }
}
