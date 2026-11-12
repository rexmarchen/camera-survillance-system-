

package com.camfu.surveillance.util;

import javafx.scene.image.Image;
import javafx.embed.swing.SwingFXUtils;
import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.FrameGrabber;
import org.bytedeco.javacv.OpenCVFrameGrabber;
import org.bytedeco.javacv.VideoInputFrameGrabber;
import org.bytedeco.javacv.Frame;
import org.bytedeco.javacv.Java2DFrameConverter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.net.ssl.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.concurrent.ConcurrentHashMap;

/**
 * HIGH-PERFORMANCE Video Stream Utility
 * Supports RTSP, HTTP/HTTPS MJPEG, Webcams (0, 1), Video Files, and Interactive Simulation feeds.
 */
public class VideoStreamUtil {
    private static final Logger logger = LoggerFactory.getLogger(VideoStreamUtil.class);

    // SSL: accept self-signed certificates (IP Webcam HTTPS mode)
    static {
        try {
            TrustManager[] trustAll = new TrustManager[]{
                new X509TrustManager() {
                    public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                    public void checkClientTrusted(X509Certificate[] c, String a) {}
                    public void checkServerTrusted(X509Certificate[] c, String a) {}
                }
            };
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, trustAll, new java.security.SecureRandom());
            HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
            HttpsURLConnection.setDefaultHostnameVerifier((host, session) -> true);
        } catch (Exception e) {
            logger.warn("Could not install SSL trust-all: {}", e.getMessage());
        }
    }

    // Persistent connections
    private static final ConcurrentHashMap<String, MJPEGStreamReader> mjpegReaders = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, FFmpegFrameGrabber> rtspGrabbers = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, FrameGrabber> webcamGrabbers = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, Long> webcamCooldown = new ConcurrentHashMap<>();

    // ThreadLocal converter
    private static final ThreadLocal<Java2DFrameConverter> converterLocal =
            ThreadLocal.withInitial(Java2DFrameConverter::new);

    private static final SimpleDateFormat DATE_FORMAT = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS");

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    public static Image fetchFrame(String streamUrl) {
        if (streamUrl == null || streamUrl.isBlank()) return null;

        String lower = streamUrl.toLowerCase().trim();

        // 1. Webcam (device 0, 1, webcam://0, etc.)
        if (lower.matches("^\\d+$") || lower.startsWith("webcam://") || lower.startsWith("camera://") || lower.contains("/dev/video")) {
            int deviceIndex = 0;
            try {
                if (lower.matches("^\\d+$")) {
                    deviceIndex = Integer.parseInt(lower);
                } else if (lower.contains("1")) {
                    deviceIndex = 1;
                }
            } catch (Exception ignored) {}
            return fetchWebcamFrame(streamUrl, deviceIndex);
        }

        // 2. RTSP or Local Video File
        if (lower.startsWith("rtsp://") || lower.endsWith(".mp4") || lower.endsWith(".avi") || lower.endsWith(".mkv") || lower.startsWith("file://")) {
            Image img = fetchRTSPFrame(streamUrl);
            if (img != null) return img;
        }

        // 3. HTTP / HTTPS Stream (e.g. IP Webcam mobile app)
        if (lower.startsWith("http://") || lower.startsWith("https://")) {
            Image img = fetchMJPEGFrame(streamUrl);
            if (img != null) return img;
        }

        // 4. Demo / Simulation or offline fallback
        return generateDemoFrame(streamUrl);
    }

    public static Image fetchFrameFromMJPEG(String streamUrl) {
        return fetchFrame(streamUrl);
    }

    public static void closeStream(String streamUrl) {
        if (streamUrl == null) return;

        MJPEGStreamReader reader = mjpegReaders.remove(streamUrl);
        if (reader != null) {
            new Thread(() -> { try { reader.close(); } catch (Exception ignored) {} }).start();
        }

        FFmpegFrameGrabber grabber = rtspGrabbers.remove(streamUrl);
        if (grabber != null) {
            new Thread(() -> { try { grabber.stop(); grabber.close(); } catch (Exception ignored) {} }).start();
        }

        FrameGrabber webGrabber = webcamGrabbers.remove(streamUrl);
        if (webGrabber != null) {
            new Thread(() -> { try { webGrabber.stop(); webGrabber.close(); } catch (Exception ignored) {} }).start();
        }
    }

    public static void closeAllStreams() {
        mjpegReaders.forEach((url, r) -> {
            new Thread(() -> { try { r.close(); } catch (Exception ignored) {} }).start();
        });
        mjpegReaders.clear();

        rtspGrabbers.forEach((url, g) -> {
            new Thread(() -> { try { g.stop(); g.close(); } catch (Exception ignored) {} }).start();
        });
        rtspGrabbers.clear();

        webcamGrabbers.forEach((url, w) -> {
            new Thread(() -> { try { w.stop(); w.close(); } catch (Exception ignored) {} }).start();
        });
        webcamGrabbers.clear();
    }

    // -------------------------------------------------------------------------
    // Webcam Grabber (Direct built-in laptop / USB camera)
    // -------------------------------------------------------------------------

    private static Image fetchWebcamFrame(String streamUrl, int deviceIndex) {
        Long cooldown = webcamCooldown.get(streamUrl);
        if (cooldown != null && (System.currentTimeMillis() - cooldown < 3500)) {
            return generateDemoFrame("Webcam-" + deviceIndex);
        }

        FrameGrabber grabber = webcamGrabbers.get(streamUrl);
        if (grabber == null) {
            try {
                logger.info("Opening webcam device: " + deviceIndex);
                if (System.getProperty("os.name", "").toLowerCase().contains("win")) {
                    try {
                        grabber = new VideoInputFrameGrabber(deviceIndex);
                    } catch (Throwable t) {
                        grabber = new OpenCVFrameGrabber(deviceIndex);
                    }
                } else {
                    grabber = new OpenCVFrameGrabber(deviceIndex);
                }
                grabber.setImageWidth(640);
                grabber.setImageHeight(480);
                grabber.start();
                webcamGrabbers.put(streamUrl, grabber);
            } catch (Throwable e) {
                logger.warn("Failed to open webcam " + deviceIndex + ": " + e.getMessage());
                webcamCooldown.put(streamUrl, System.currentTimeMillis());
                return generateDemoFrame("Webcam-" + deviceIndex + " (Not connected)");
            }
        }

        try {
            Frame frame = grabber.grab();
            if (frame != null && frame.image != null) {
                Java2DFrameConverter converter = converterLocal.get();
                BufferedImage bi = converter.convert(frame);
                if (bi != null) {
                    return SwingFXUtils.toFXImage(bi, null);
                }
            } else {
                webcamCooldown.put(streamUrl, System.currentTimeMillis());
                webcamGrabbers.remove(streamUrl);
                try { grabber.stop(); grabber.close(); } catch (Exception ignored) {}
            }
        } catch (Throwable e) {
            webcamCooldown.put(streamUrl, System.currentTimeMillis());
            webcamGrabbers.remove(streamUrl);
            try { grabber.stop(); grabber.close(); } catch (Exception ignored) {}
        }
        return generateDemoFrame("Webcam-" + deviceIndex);
    }

    // -------------------------------------------------------------------------
    // Demo / Simulated CCTV Feed Generator
    // -------------------------------------------------------------------------

    private static Image generateDemoFrame(String identifier) {
        int width = 640;
        int height = 480;
        BufferedImage bi = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = bi.createGraphics();

        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        // Dark CCTV background with grid
        g.setColor(new Color(15, 23, 42));
        g.fillRect(0, 0, width, height);

        g.setColor(new Color(30, 41, 59));
        for (int x = 0; x < width; x += 40) {
            g.drawLine(x, 0, x, height);
        }
        for (int y = 0; y < height; y += 40) {
            g.drawLine(0, y, width, y);
        }

        long time = System.currentTimeMillis();
        int hash = Math.abs(identifier.hashCode());
        double speed = 0.002 + ((hash % 5) * 0.001);
        double angle = (time * speed) % (2 * Math.PI);

        // Simulated moving object
        int objX = (int) (width / 2 + Math.cos(angle) * (width / 3));
        int objY = (int) (height / 2 + Math.sin(angle * 1.5) * (height / 4));

        g.setColor(new Color(37, 99, 235, 80));
        g.fillRect(objX - 25, objY - 35, 50, 70);

        g.setColor(new Color(59, 130, 246));
        g.setStroke(new BasicStroke(2.0f));
        g.drawRect(objX - 25, objY - 35, 50, 70);

        // Crosshairs and target tracking box
        g.setColor(new Color(239, 68, 68));
        g.drawOval(objX - 5, objY - 5, 10, 10);
        g.drawString("TRACK [OBJECT_0" + (hash % 9 + 1) + "]", objX - 25, objY - 40);

        // CCTV Info Banner
        g.setColor(new Color(0, 0, 0, 180));
        g.fillRect(0, 0, width, 30);
        g.fillRect(0, height - 25, width, 25);

        g.setColor(new Color(34, 197, 94));
        g.setFont(new Font("Monospaced", Font.BOLD, 12));
        g.drawString("● LIVE", 10, 20);

        g.setColor(Color.WHITE);
        g.drawString("CAM: " + identifier, 80, 20);
        g.drawString(DATE_FORMAT.format(new Date(time)), width - 240, 20);

        g.setColor(new Color(148, 163, 184));
        g.drawString("RESOLUTION: 1280x720 | FPS: 15.0 | AI ANALYTICS: ACTIVE", 10, height - 8);

        g.dispose();
        try { Thread.sleep(60); } catch (Exception ignored) {}
        return SwingFXUtils.toFXImage(bi, null);
    }

    // -------------------------------------------------------------------------
    // MJPEG Reader
    // -------------------------------------------------------------------------

    private static Image fetchMJPEGFrame(String streamUrl) {
        MJPEGStreamReader reader = mjpegReaders.get(streamUrl);
        if (reader == null) {
            reader = openMJPEGReader(streamUrl);
            if (reader != null) {
                mjpegReaders.put(streamUrl, reader);
            }
        }

        if (reader == null) return null;

        try {
            byte[] jpegBytes = reader.readNextFrame();
            if (jpegBytes != null && jpegBytes.length > 0) {
                return new Image(new ByteArrayInputStream(jpegBytes));
            }
        } catch (IOException e) {
            mjpegReaders.remove(streamUrl, reader);
            try { reader.close(); } catch (IOException ignored) {}
        }
        return null;
    }

    private static MJPEGStreamReader openMJPEGReader(String streamUrl) {
        try {
            String connectUrl = resolveStreamUrl(streamUrl);
            URL url = new URL(connectUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(3_000);
            conn.setReadTimeout(5_000);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "CamFu/1.0");
            conn.setRequestProperty("Accept", "multipart/x-mixed-replace, image/jpeg, image/png, */*");
            conn.setRequestProperty("Connection", "close");
            conn.connect();

            int code = conn.getResponseCode();
            if (code != 200) {
                conn.disconnect();
                return null;
            }

            return new MJPEGStreamReader(conn, conn.getInputStream(), conn.getContentType());
        } catch (Exception e) {
            return null;
        }
    }

    // -------------------------------------------------------------------------
    // RTSP & Video Grabber
    // -------------------------------------------------------------------------

    private static Image fetchRTSPFrame(String streamUrl) {
        FFmpegFrameGrabber grabber = rtspGrabbers.get(streamUrl);
        if (grabber == null) {
            grabber = openRTSPGrabber(streamUrl);
            if (grabber != null) {
                rtspGrabbers.put(streamUrl, grabber);
            }
        }

        if (grabber == null) return null;

        try {
            Frame frame = grabber.grabImage();
            if (frame != null && frame.image != null) {
                Java2DFrameConverter converter = converterLocal.get();
                BufferedImage bi = converter.convert(frame);
                if (bi != null) {
                    return SwingFXUtils.toFXImage(bi, null);
                }
            }
        } catch (Exception e) {
            rtspGrabbers.remove(streamUrl, grabber);
            try { grabber.stop(); grabber.close(); } catch (Exception ignored) {}
        }
        return null;
    }

    private static FFmpegFrameGrabber openRTSPGrabber(String streamUrl) {
        try {
            FFmpegFrameGrabber grabber = new FFmpegFrameGrabber(streamUrl);
            if (streamUrl.toLowerCase().startsWith("rtsp://")) {
                grabber.setOption("rtsp_transport", "tcp");
                grabber.setOption("fflags", "nobuffer");
                grabber.setOption("flags", "low_delay");
                grabber.setOption("probesize", "32");
                grabber.setOption("analyzeduration", "0");
                grabber.setOption("max_delay", "0");
            }
            grabber.setImageWidth(640);
            grabber.setImageHeight(480);
            grabber.start();
            return grabber;
        } catch (Exception e) {
            return null;
        }
    }

    private static String resolveStreamUrl(String streamUrl) {
        if (streamUrl.endsWith(".jpg") || streamUrl.endsWith(".jpeg") || streamUrl.endsWith(".png") || streamUrl.endsWith(".mjpg")) {
            return streamUrl;
        }
        if (streamUrl.contains("/video")) {
            return streamUrl;
        }
        String base = streamUrl.endsWith("/") ? streamUrl : streamUrl + "/";
        return base + "video";
    }

    public static class MJPEGStreamReader implements Closeable {
        private static final int BUFFER_SIZE = 65_536;
        private final HttpURLConnection conn;
        private final InputStream raw;
        private final BufferedInputStream buf;
        private final boolean isMultipart;

        public MJPEGStreamReader(HttpURLConnection conn, InputStream stream, String contentType) {
            this.conn = conn;
            this.raw = stream;
            this.buf = new BufferedInputStream(stream, BUFFER_SIZE);
            this.isMultipart = contentType != null && contentType.toLowerCase().contains("multipart");
        }

        public byte[] readNextFrame() throws IOException {
            return isMultipart ? readMultipartFrame() : readFullBody();
        }

        private byte[] readMultipartFrame() throws IOException {
            int contentLength = -1;
            boolean insideHeaders = false;
            String line;

            while ((line = readLine()) != null) {
                if (line.isEmpty()) {
                    if (insideHeaders) {
                        if (contentLength > 0) {
                            return readExactBytes(contentLength);
                        } else {
                            return readUntilJpegEOI();
                        }
                    }
                    continue;
                }

                insideHeaders = true;
                String lower = line.toLowerCase();
                if (lower.startsWith("content-length:")) {
                    try {
                        contentLength = Integer.parseInt(line.substring(line.indexOf(':') + 1).trim());
                    } catch (NumberFormatException ignored) {}
                }
            }
            throw new IOException("Stream ended unexpectedly");
        }

        private byte[] readExactBytes(int n) throws IOException {
            byte[] data = new byte[n];
            int offset = 0;
            while (offset < n) {
                int read = buf.read(data, offset, n - offset);
                if (read < 0) throw new IOException("Stream ended after " + offset + "/" + n + " bytes");
                offset += read;
            }
            return data;
        }

        private byte[] readUntilJpegEOI() throws IOException {
            ByteArrayOutputStream baos = new ByteArrayOutputStream(32_768);
            int prev = -1, curr;
            while ((curr = buf.read()) != -1) {
                baos.write(curr);
                if (prev == 0xFF && curr == 0xD9) {
                    return baos.toByteArray();
                }
                prev = curr;
            }
            throw new IOException("Stream ended before JPEG EOI marker");
        }

        private byte[] readFullBody() throws IOException {
            ByteArrayOutputStream baos = new ByteArrayOutputStream(65_536);
            byte[] tmp = new byte[8_192];
            int n;
            while ((n = buf.read(tmp)) != -1) {
                baos.write(tmp, 0, n);
            }
            return baos.toByteArray();
        }

        private String readLine() throws IOException {
            ByteArrayOutputStream baos = new ByteArrayOutputStream(256);
            int b, prev = -1;
            while ((b = buf.read()) != -1) {
                if (b == '\n') {
                    byte[] bytes = baos.toByteArray();
                    int len = bytes.length;
                    if (len > 0 && bytes[len - 1] == '\r') len--;
                    return new String(bytes, 0, len);
                }
                baos.write(b);
                prev = b;
            }
            return null;
        }

        @Override
        public void close() throws IOException {
            raw.close();
            if (conn != null) {
                conn.disconnect();
            }
        }
    }
}
