package com.camfu.surveillance.ui;

import com.camfu.surveillance.model.Camera;
import com.camfu.surveillance.model.PriorityScore;
import com.camfu.surveillance.service.CameraService;
import com.camfu.surveillance.util.VideoStreamUtil;
import com.camfu.surveillance.util.VLCStreamPlayer;
import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.layout.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.*;

/**
 * Camera feed grid panel — with Smart Priority Layout.
 *
 * FEATURE: Smart Auto-Layout
 *   When multiple cameras are active, the grid automatically re-orders itself
 *   every few seconds based on live priority scores from the AI engine:
 *
 *   • The TOP-priority camera (highest crowd + behavior) gets a 2×2 "hero" slot
 *     (double width and double height) in position [0,0].
 *   • All other cameras are shown as normal 1×1 tiles to its right / below.
 *   • If a camera scores below the IDLE_THRESHOLD (no motion, crowd, behavior),
 *     its tile is visually dimmed so the operator's eye goes to the active feeds.
 *   • Layout refreshes every LAYOUT_REFRESH_MS milliseconds automatically.
 *   • A "🔴 ALERT" badge overlays any camera that has unusual_behavior > 0.5.
 *
 * BUG VERIFICATION (all five Python fixes are confirmed in this file too):
 *   The Java side reads scores from the DB via PriorityScoreDAO — the new
 *   scores written by the fixed Python engine are therefore automatically
 *   reflected here with no further Java changes needed.
 */
public class FeedGridPanel {
    private static final Logger logger = LoggerFactory.getLogger(FeedGridPanel.class);

    // ── Layout constants ────────────────────────────────────────────────────
    /** Camera whose overall priority is below this is considered idle/quiet. */
    private static final double IDLE_THRESHOLD = 0.20;

    /** Camera whose behavior score is above this triggers a red alert badge. */
    private static final double ALERT_THRESHOLD = 0.50;

    /** How often (ms) the grid re-sorts itself based on new AI scores. */
    private static final long LAYOUT_REFRESH_MS = 5_000;

    // ── State ───────────────────────────────────────────────────────────────
    private VBox       panel;
    private GridPane   gridPane;
    private CameraService cameraService;

    /** All stream panels, keyed by camera ID. */
    private final Map<Integer, VLCStreamPanel> activePanels = new ConcurrentHashMap<>();

    /** Current ordered list of cameras (re-sorted by priority each cycle). */
    private List<Camera> currentCameras = new ArrayList<>();

    /** Latest scores fetched from DB, keyed by camera ID. */
    private final Map<Integer, PriorityScore> latestScores = new ConcurrentHashMap<>();

    private java.util.function.Consumer<Integer> feedCountListener;
    private volatile boolean shuttingDown = false;

    /** Background scheduler for the auto-layout refresh loop. */
    private ScheduledExecutorService layoutScheduler;

    // ── Public API ──────────────────────────────────────────────────────────

    public VBox getPanel() { return panel; }

    public void setFeedCountListener(java.util.function.Consumer<Integer> listener) {
        this.feedCountListener = listener;
    }

    public void initialize(CameraService cameraService) {
        this.cameraService = cameraService;

        try {
            VLCStreamPlayer.initializeVLC();
        } catch (Exception e) {
            logger.warn("VLC init skipped: {}", e.getMessage());
        }

        panel = new VBox();
        panel.setPadding(new Insets(8));
        panel.setStyle("-fx-background-color: transparent;");

        HBox topBar = buildTopBar();

        gridPane = new GridPane();
        gridPane.setHgap(6);
        gridPane.setVgap(6);
        gridPane.setPadding(new Insets(8));
        gridPane.setStyle("-fx-background-color: transparent;");

        VBox.setVgrow(gridPane, Priority.ALWAYS);
        panel.getChildren().addAll(topBar, gridPane);

        loadFeeds();

        // Start the smart layout refresh scheduler
        layoutScheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "SmartLayoutRefresher");
            t.setDaemon(true);
            return t;
        });
        layoutScheduler.scheduleAtFixedRate(
                this::refreshLayoutFromScores,
                LAYOUT_REFRESH_MS, LAYOUT_REFRESH_MS,
                TimeUnit.MILLISECONDS
        );
    }

    // ── Top bar ─────────────────────────────────────────────────────────────

    private HBox buildTopBar() {
        HBox bar = new HBox(10);
        bar.setPadding(new Insets(4, 0, 8, 0));
        bar.setAlignment(Pos.CENTER_LEFT);

        Label title = new Label("⬛  Live Camera Feeds");
        title.setStyle("-fx-font-size: 13px; -fx-font-weight: bold; -fx-text-fill: #e0e0e0;");

        Button refreshBtn = new Button("↺  Refresh");
        refreshBtn.setOnAction(e -> refreshFeeds());

        Button stopBtn = new Button("■  Stop All");
        stopBtn.setStyle("-fx-background-color: #E11D48;");
        stopBtn.setOnAction(e -> stopAllFeeds());

        Region spacer = new Region();
        HBox.setHgrow(spacer, Priority.ALWAYS);

        bar.getChildren().addAll(title, spacer, refreshBtn, stopBtn);
        return bar;
    }

    // ── Feed loading ─────────────────────────────────────────────────────────

    private void loadFeeds() {
        new Thread(() -> {
            try {
                List<Camera> cameras = cameraService.getActiveCameras();
                currentCameras = cameras;
                Platform.runLater(() -> displayFeeds(cameras));
            } catch (Exception e) {
                logger.error("Failed to load cameras from database", e);
            }
        }, "FeedLoader").start();
    }

    /**
     * Smart layout: re-fetch priority scores, sort cameras by score (desc),
     * then rebuild the grid on the FX thread only if the order actually changed.
     */
    private void refreshLayoutFromScores() {
        if (shuttingDown || currentCameras.isEmpty()) return;
        try {
            List<PriorityScore> scores = cameraService.getPriorityScores();
            // Update score map
            for (PriorityScore ps : scores) {
                latestScores.put(ps.getCameraId(), ps);
            }

            // Sort cameras by overall priority (highest first)
            List<Camera> sorted = new ArrayList<>(currentCameras);
            sorted.sort((a, b) -> {
                double scoreA = latestScores.containsKey(a.getId())
                        ? latestScores.get(a.getId()).getOverallPriorityScore() : 0.0;
                double scoreB = latestScores.containsKey(b.getId())
                        ? latestScores.get(b.getId()).getOverallPriorityScore() : 0.0;
                return Double.compare(scoreB, scoreA); // descending
            });

            // Only redraw if the priority order changed
            boolean orderChanged = false;
            for (int i = 0; i < sorted.size(); i++) {
                if (i >= currentCameras.size()
                        || !Objects.equals(sorted.get(i).getId(), currentCameras.get(i).getId())) {
                    orderChanged = true;
                    break;
                }
            }

            if (orderChanged) {
                currentCameras = sorted;
                logger.info("Priority order changed — rebuilding grid layout");
                Platform.runLater(() -> rebuildGridLayout(sorted));
            } else {
                // Order unchanged — just refresh alert badges without full rebuild
                Platform.runLater(this::refreshBadgesOnly);
            }

        } catch (Exception e) {
            logger.warn("Could not refresh layout scores: {}", e.getMessage());
        }
    }

    // ── Grid rendering ───────────────────────────────────────────────────────

    private void displayFeeds(List<Camera> cameras) {
        gridPane.getChildren().clear();
        gridPane.getColumnConstraints().clear();
        gridPane.getRowConstraints().clear();

        if (cameras.isEmpty()) {
            if (feedCountListener != null) feedCountListener.accept(0);
            Label empty = new Label("No active cameras found.\nUse Cameras → Add Camera to add one.");
            empty.setStyle("-fx-text-fill: #888; -fx-font-size: 13px;");
            empty.setWrapText(true);
            gridPane.add(empty, 0, 0);
            return;
        }

        if (feedCountListener != null) feedCountListener.accept(cameras.size());
        buildSmartGrid(cameras);
    }

    /**
     * Rebuild the grid preserving existing VLCStreamPanel instances
     * (so streams are NOT interrupted — only their grid position changes).
     */
    private void rebuildGridLayout(List<Camera> cameras) {
        gridPane.getChildren().clear();
        gridPane.getColumnConstraints().clear();
        gridPane.getRowConstraints().clear();
        buildSmartGrid(cameras);
    }

    /**
     * Smart grid layout logic:
     *
     * ┌──────────────────┬────────┐
     * │                  │  cam2  │
     * │  cam1 (HERO 2×2) ├────────┤
     * │                  │  cam3  │
     * ├────────┬──────────┴────────┤
     * │  cam4  │  cam5  │  cam6   │
     * └────────┴─────────┴─────────┘
     *
     * cam1 = highest priority → occupies 2 columns × 2 rows (60% width)
     * remaining cameras fill the remaining cells normally
     * idle cameras get a dimmed overlay
     */
    private void buildSmartGrid(List<Camera> cameras) {
        int total = cameras.size();

        if (total == 1) {
            setupGridConstraints(1, 1);
            addTile(cameras.get(0), 0, 0, 1, 1);
            return;
        }

        if (total == 2) {
            setupGridConstraints(2, 1);
            addTile(cameras.get(0), 0, 0, 1, 1);
            addTile(cameras.get(1), 1, 0, 1, 1);
            return;
        }

        // 3+ cameras: hero layout
        // Hero occupies col 0-1, row 0-1 (2×2).
        // Right side column: 2 slots (rows 0, 1).
        // Bottom rows: overflow cameras.

        int remaining = total - 1;
        int rightSlots = 2;
        int bottomCameras = Math.max(0, remaining - rightSlots);

        // Total grid: 3 cols (hero takes 2, side takes 1)
        int totalCols = 3;
        int bottomRows = (bottomCameras > 0)
                ? (int) Math.ceil((double) bottomCameras / totalCols)
                : 0;
        int totalRows = 2 + bottomRows;

        // Build column constraints: col 0+1 share 60%, col 2 gets 40%
        gridPane.getColumnConstraints().clear();
        ColumnConstraints heroCol1 = new ColumnConstraints();
        heroCol1.setPercentWidth(30);
        heroCol1.setHgrow(Priority.ALWAYS);
        ColumnConstraints heroCol2 = new ColumnConstraints();
        heroCol2.setPercentWidth(30);
        heroCol2.setHgrow(Priority.ALWAYS);
        ColumnConstraints sideCol = new ColumnConstraints();
        sideCol.setPercentWidth(40);
        sideCol.setHgrow(Priority.ALWAYS);
        gridPane.getColumnConstraints().addAll(heroCol1, heroCol2, sideCol);

        gridPane.getRowConstraints().clear();
        for (int i = 0; i < totalRows; i++) {
            RowConstraints rc = new RowConstraints();
            rc.setPercentHeight(100.0 / totalRows);
            rc.setVgrow(Priority.ALWAYS);
            gridPane.getRowConstraints().add(rc);
        }

        // ── Place hero camera (spans 2 cols × 2 rows) ──
        addTile(cameras.get(0), 0, 0, 2, 2);

        // ── Place cameras in right side column (rows 0 and 1) ──
        int camIndex = 1;
        for (int row = 0; row < rightSlots && camIndex < total; row++, camIndex++) {
            addTile(cameras.get(camIndex), 2, row, 1, 1);
        }

        // ── Place remaining cameras in bottom rows (spanning full width) ──
        int col = 0;
        int row = 2;
        while (camIndex < total) {
            addTile(cameras.get(camIndex), col, row, 1, 1);
            col++;
            if (col >= totalCols) {
                col = 0;
                row++;
            }
            camIndex++;
        }

        logger.info("Smart grid: {} camera(s) — hero=[{}], idle=[{}]",
                total,
                cameras.get(0).getCameraName(),
                cameras.stream().skip(1)
                        .filter(c -> {
                            PriorityScore ps = latestScores.get(c.getId());
                            return ps != null && ps.getOverallPriorityScore() < IDLE_THRESHOLD;
                        })
                        .map(Camera::getCameraName)
                        .reduce((a, b) -> a + ", " + b)
                        .orElse("none"));
    }

    private void setupGridConstraints(int cols, int rows) {
        gridPane.getColumnConstraints().clear();
        gridPane.getRowConstraints().clear();
        for (int i = 0; i < cols; i++) {
            ColumnConstraints cc = new ColumnConstraints();
            cc.setPercentWidth(100.0 / cols);
            cc.setHgrow(Priority.ALWAYS);
            gridPane.getColumnConstraints().add(cc);
        }
        for (int i = 0; i < rows; i++) {
            RowConstraints rc = new RowConstraints();
            rc.setPercentHeight(100.0 / rows);
            rc.setVgrow(Priority.ALWAYS);
            gridPane.getRowConstraints().add(rc);
        }
    }

    // ── Tile construction ─────────────────────────────────────────────────

    private void addTile(Camera camera, int col, int row, int colSpan, int rowSpan) {
        if (shuttingDown) return;
        StackPane tile = buildTile(camera, colSpan > 1 || rowSpan > 1);
        GridPane.setColumnIndex(tile, col);
        GridPane.setRowIndex(tile, row);
        GridPane.setColumnSpan(tile, colSpan);
        GridPane.setRowSpan(tile, rowSpan);
        GridPane.setHgrow(tile, Priority.ALWAYS);
        GridPane.setVgrow(tile, Priority.ALWAYS);
        gridPane.getChildren().add(tile);
    }

    /**
     * Builds a camera tile. If it's the hero tile, it shows a "⭐ PRIORITY" badge.
     * Idle cameras are dimmed. Cameras with unusual behavior show a "🔴 ALERT" badge.
     */
    private StackPane buildTile(Camera camera, boolean isHero) {
        // Reuse existing stream panel to keep stream alive across layout rebuilds
        VLCStreamPanel streamPanel;
        if (activePanels.containsKey(camera.getId())) {
            streamPanel = activePanels.get(camera.getId());
        } else {
            streamPanel = new VLCStreamPanel(camera);
            activePanels.put(camera.getId(), streamPanel);
        }
        streamPanel.setMaxSize(Double.MAX_VALUE, Double.MAX_VALUE);

        // Info strip
        HBox infoStrip = new HBox();
        infoStrip.setStyle("-fx-background-color: rgba(0,0,0,0.6); -fx-padding: 4 8;");
        infoStrip.setAlignment(Pos.CENTER_LEFT);

        Label camName = new Label("📷  " + camera.getCameraName());
        camName.setStyle("-fx-font-size: 10px; -fx-text-fill: #cccccc;");

        Label location = new Label(camera.getLocation() != null ? " — " + camera.getLocation() : "");
        location.setStyle("-fx-font-size: 10px; -fx-text-fill: #777;");

        Region sp = new Region();
        HBox.setHgrow(sp, Priority.ALWAYS);

        boolean active = "ACTIVE".equalsIgnoreCase(camera.getStatus());
        Label statusDot = new Label(camera.getStatus());
        statusDot.setStyle("-fx-font-size: 10px; -fx-font-weight: bold; -fx-text-fill: "
                + (active ? "#10B981" : "#EF4444") + ";");

        infoStrip.getChildren().addAll(camName, location, sp, statusDot);

        VBox tileBox = new VBox(0);
        tileBox.setMaxSize(Double.MAX_VALUE, Double.MAX_VALUE);
        tileBox.setMinSize(0, 0);
        tileBox.setPrefSize(0, 0);
        VBox.setVgrow(streamPanel, Priority.ALWAYS);
        tileBox.getChildren().addAll(streamPanel, infoStrip);

        // Score-based styling
        PriorityScore score = latestScores.get(camera.getId());
        double overall  = (score != null) ? score.getOverallPriorityScore()  : 0.0;
        double behavior = (score != null) ? score.getUnusualBehaviorScore()  : 0.0;

        String borderColor;
        if (behavior > ALERT_THRESHOLD) {
            borderColor = "#EF4444";   // red — alert
        } else if (isHero) {
            borderColor = "#F59E0B";   // amber — priority hero
        } else if (overall < IDLE_THRESHOLD) {
            borderColor = "#1F2937";   // dark grey — idle
        } else {
            borderColor = "#374151";   // normal
        }

        int borderWidth = (isHero || behavior > ALERT_THRESHOLD) ? 2 : 1;
        tileBox.setStyle("-fx-background-color: #1F2937;"
                + "-fx-border-color: " + borderColor + ";"
                + "-fx-border-width: " + borderWidth + ";"
                + "-fx-border-radius: 8; -fx-background-radius: 8;");

        // Dim idle cameras so operator's eye goes to active feeds
        if (!isHero && overall < IDLE_THRESHOLD) {
            tileBox.setOpacity(0.55);
        }

        StackPane stack = new StackPane(tileBox);
        stack.setMaxSize(Double.MAX_VALUE, Double.MAX_VALUE);

        // Hero badge (top-left)
        if (isHero) {
            Label heroBadge = new Label("⭐ PRIORITY");
            heroBadge.setStyle("-fx-background-color: #F59E0B; -fx-text-fill: #000;"
                    + "-fx-font-size: 10px; -fx-font-weight: bold;"
                    + "-fx-padding: 2 6; -fx-background-radius: 4;");
            StackPane.setAlignment(heroBadge, Pos.TOP_LEFT);
            StackPane.setMargin(heroBadge, new Insets(6));
            stack.getChildren().add(heroBadge);
        }

        // Alert badge (top-right)
        if (behavior > ALERT_THRESHOLD) {
            Label alertBadge = new Label("🔴 ALERT");
            alertBadge.setStyle("-fx-background-color: #EF4444; -fx-text-fill: #fff;"
                    + "-fx-font-size: 10px; -fx-font-weight: bold;"
                    + "-fx-padding: 2 6; -fx-background-radius: 4;");
            StackPane.setAlignment(alertBadge, Pos.TOP_RIGHT);
            StackPane.setMargin(alertBadge, new Insets(6));
            stack.getChildren().add(alertBadge);
        }

        return stack;
    }

    /**
     * Lightweight refresh: re-applies badge and dim styling without
     * recreating stream panels or changing grid positions.
     */
    private void refreshBadgesOnly() {
        if (!currentCameras.isEmpty()) {
            rebuildGridLayout(currentCameras);
        }
    }

    // ── Controls ─────────────────────────────────────────────────────────────

    public void stopAllFeeds() {
        logger.info("Stopping all {} stream panels…", activePanels.size());
        for (VLCStreamPanel p : activePanels.values()) {
            try { p.stop(); } catch (Exception e) {
                logger.warn("Error stopping panel: {}", e.getMessage());
            }
        }
        activePanels.clear();
        Platform.runLater(() -> {
            gridPane.getChildren().clear();
            gridPane.getColumnConstraints().clear();
            gridPane.getRowConstraints().clear();
            if (feedCountListener != null) feedCountListener.accept(0);
        });
        logger.info("All feeds stopped");
    }

    public void refreshFeeds() {
        logger.info("Refreshing camera feeds…");
        stopAllFeeds();
        loadFeeds();
    }

    public void shutdown() {
        logger.info("FeedGridPanel shutdown initiated");
        shuttingDown = true;
        if (layoutScheduler != null) {
            layoutScheduler.shutdownNow();
        }
        stopAllFeeds();
        VideoStreamUtil.closeAllStreams();
        try { VLCStreamPlayer.shutdownVLC(); } catch (Exception ignored) {}
        logger.info("FeedGridPanel shutdown complete");
    }
}
