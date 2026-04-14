from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from tuition_planner.charts import (
    monthly_spending_figure,
    savings_figure,
    spending_breakdown_figure,
    tuition_figure,
)

from tuition_planner.csv_mapping import ColumnMappingDialog
from tuition_planner.data_loader import load_spending_history, load_tuition_history
from tuition_planner.database import ScenarioRepository
from tuition_planner.excel_export import export_workbook
from tuition_planner.forecasting import TuitionForecaster
from tuition_planner.models import ForecastBundle, SpendingInsights
from tuition_planner.savings import (
    DEFAULT_PROFILES,
    build_savings_recommendations,
    future_value_schedule,
    get_profile,
    required_monthly_contribution,
)
from tuition_planner.spending_analysis import analyze_spending


ROOT_DIR = Path(__file__).resolve().parents[1]
TUITION_CSV = ROOT_DIR / "EngineeringTuitionData.csv"
SAMPLE_SPENDING_CSV = ROOT_DIR / "data" / "sample_spending.csv"
DATABASE_PATH = ROOT_DIR / "data" / "tuition_planner.db"
EXPORTS_DIR = ROOT_DIR / "exports"

APP_BG = "#F6F1E7"
CARD_BG = "#FFF9F0"
CARD_BORDER = "#D7C7AE"
PRIMARY = "#264653"
SECONDARY = "#E76F51"
TEXT = "#2B2D42"
MUTED = "#6C757D"

FONT_PRESETS = {
    "Standard": {"base": 10, "section": 11, "card": 12, "metric": 18, "header": 24},
    "Large": {"base": 12, "section": 13, "card": 14, "metric": 22, "header": 28},
    "Extra Large": {
        "base": 14,
        "section": 15,
        "card": 16,
        "metric": 26,
        "header": 32,
    },
}


class TuitionPlannerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Tuition Forecasting & Financial Planning")
        self.geometry("1440x940")
        self.minsize(1180, 760)
        self.configure(bg=APP_BG)

        self.tuition_history = load_tuition_history(TUITION_CSV)
        self.forecaster = TuitionForecaster(self.tuition_history).fit()
        self.repository = ScenarioRepository(DATABASE_PATH)
        self.current_bundle: ForecastBundle | None = None
        self.current_spending: SpendingInsights | None = None
        self.figure_canvases: dict[str, FigureCanvasTkAgg] = {}
        self.spending_column_mapping: dict[str, str] | None = None
        self.history_item_ids: dict[str, int] = {}

        self._build_variables()
        self._create_fonts()
        self._configure_styles()
        self._build_layout()
        self.apply_font_preset(initial=True)
        self.refresh_history()
        self.run_forecast(save_to_history=False)

    def _build_variables(self) -> None:
        target_year = max(date.today().year + 2, self.forecaster.max_year + 1)
        self.scenario_name_var = tk.StringVar(value="Engineering Tuition Plan")
        self.current_balance_var = tk.StringVar(value="15000")
        self.monthly_contribution_var = tk.StringVar(value="650")
        self.target_year_var = tk.StringVar(value=str(target_year))
        self.target_month_var = tk.StringVar(value="9")
        self.degree_years_var = tk.StringVar(value="4")
        self.risk_profile_var = tk.StringVar(value="TD-style basic savings")
        self.annual_return_var = tk.StringVar(value="0.01")
        self.spending_file_var = tk.StringVar(value=str(SAMPLE_SPENDING_CSV))
        self.monthly_income_var = tk.StringVar(value="3400")
        self.target_extra_savings_var = tk.StringVar(value="0")
        self.font_preset_var = tk.StringVar(value="Standard")
        self.mapping_status_var = tk.StringVar(
            value="CSV mapping: automatic detection enabled"
        )

    def _create_fonts(self) -> None:
        self.base_font = tkfont.Font(family="Segoe UI", size=10)
        self.header_font = tkfont.Font(family="Segoe UI Semibold", size=24)
        self.subheader_font = tkfont.Font(family="Segoe UI", size=11)
        self.section_font = tkfont.Font(family="Segoe UI Semibold", size=11)
        self.card_title_font = tkfont.Font(family="Segoe UI Semibold", size=12)
        self.metric_font = tkfont.Font(family="Segoe UI Semibold", size=18)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=APP_BG, foreground=TEXT, font=self.base_font)
        style.configure("Header.TLabel", font=self.header_font, foreground=PRIMARY)
        style.configure("Subheader.TLabel", font=self.subheader_font, foreground=MUTED)
        style.configure("Section.TLabelframe", background=APP_BG, bordercolor=CARD_BORDER)
        style.configure(
            "Section.TLabelframe.Label", font=self.section_font, foreground=PRIMARY
        )
        style.configure("Accent.TButton", background=PRIMARY, foreground="white", padding=(14, 9))
        style.map("Accent.TButton", background=[("active", "#1A313B")])
        style.configure("Secondary.TButton", background=SECONDARY, foreground="white", padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", "#C4553C")])
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), font=self.section_font)
        style.map("TNotebook.Tab", background=[("selected", CARD_BG)], foreground=[("selected", PRIMARY)])
        style.configure("Treeview", rowheight=28, fieldbackground="white")
        style.configure("Treeview.Heading", font=self.section_font)

    def apply_font_preset(self, *_args, initial: bool = False) -> None:
        preset = FONT_PRESETS[self.font_preset_var.get()]
        self.base_font.configure(size=preset["base"])
        self.header_font.configure(size=preset["header"])
        self.subheader_font.configure(size=max(preset["base"] + 1, 11))
        self.section_font.configure(size=preset["section"])
        self.card_title_font.configure(size=preset["card"])
        self.metric_font.configure(size=preset["metric"])
        ttk.Style(self).configure(
            "Treeview", rowheight=max(28, int(preset["base"] * 2.8))
        )
        if not initial:
            self.update_idletasks()

    def _build_layout(self) -> None:
        root = tk.Frame(self, bg=APP_BG)
        root.pack(fill="both", expand=True, padx=18, pady=16)

        header = tk.Frame(root, bg=APP_BG)
        header.pack(fill="x", pady=(0, 12))
        title_block = tk.Frame(header, bg=APP_BG)
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_block,
            text="Tuition Forecasting & Financial Planning",
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_block,
            text=(
                "Desktop app for forecasting engineering tuition, stress-testing savings plans, "
                "and turning spending data into actionable tuition-saving advice."
            ),
            style="Subheader.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        accessibility = ttk.LabelFrame(
            header, text="Display", style="Section.TLabelframe"
        )
        accessibility.pack(side="right", padx=(14, 0))
        ttk.Label(accessibility, text="Font size").grid(
            row=0, column=0, sticky="w", padx=10, pady=8
        )
        font_combo = ttk.Combobox(
            accessibility,
            textvariable=self.font_preset_var,
            values=list(FONT_PRESETS.keys()),
            state="readonly",
            width=14,
        )
        font_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        font_combo.bind("<<ComboboxSelected>>", self.apply_font_preset)

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self.planner_tab = tk.Frame(notebook, bg=APP_BG)
        self.spending_tab = tk.Frame(notebook, bg=APP_BG)
        self.history_tab = tk.Frame(notebook, bg=APP_BG)
        notebook.add(self.planner_tab, text="Planner Dashboard")
        notebook.add(self.spending_tab, text="Spending Analysis")
        notebook.add(self.history_tab, text="Scenario History")

        self._build_planner_tab()
        self._build_spending_tab()
        self._build_history_tab()

    def _build_planner_tab(self) -> None:
        self.planner_tab.columnconfigure(0, weight=0)
        self.planner_tab.columnconfigure(1, weight=1)

        control_panel = tk.Frame(self.planner_tab, bg=APP_BG, width=360)
        control_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 16), pady=(8, 8))
        content_panel = tk.Frame(self.planner_tab, bg=APP_BG)
        content_panel.grid(row=0, column=1, sticky="nsew", pady=(8, 8))

        self._build_planner_controls(control_panel)
        self._build_planner_content(content_panel)

    def _build_planner_controls(self, parent: tk.Widget) -> None:
        scenario_frame = ttk.LabelFrame(
            parent,
            text="Plan Inputs: Savings Goal and Timeline",
            style="Section.TLabelframe",
        )
        scenario_frame.pack(fill="x", pady=(0, 12))
        scenario_frame.columnconfigure(1, weight=1)

        fields = [
            ("Scenario name", self.scenario_name_var),
            ("Current savings balance", self.current_balance_var),
            ("Monthly savings contribution", self.monthly_contribution_var),
            ("Target school start year", self.target_year_var),
            ("Target start month (1-12)", self.target_month_var),
            ("Degree length (years)", self.degree_years_var),
        ]
        for row_index, (label, variable) in enumerate(fields):
            ttk.Label(scenario_frame, text=label).grid(
                row=row_index, column=0, sticky="w", padx=10, pady=7
            )
            ttk.Entry(scenario_frame, textvariable=variable).grid(
                row=row_index, column=1, sticky="ew", padx=10, pady=7
            )

        assumptions_frame = ttk.LabelFrame(
            parent,
            text="Savings Assumptions and Risk Profile",
            style="Section.TLabelframe",
        )
        assumptions_frame.pack(fill="x", pady=(0, 12))
        assumptions_frame.columnconfigure(1, weight=1)
        ttk.Label(assumptions_frame, text="Risk profile").grid(
            row=0, column=0, sticky="w", padx=10, pady=7
        )
        profile_combo = ttk.Combobox(
            assumptions_frame,
            textvariable=self.risk_profile_var,
            values=list(DEFAULT_PROFILES.keys()),
            state="readonly",
        )
        profile_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=7)
        profile_combo.bind("<<ComboboxSelected>>", self._sync_profile_return)
        ttk.Label(assumptions_frame, text="Annual return assumption (%)").grid(
            row=1, column=0, sticky="w", padx=10, pady=7
        )
        ttk.Entry(assumptions_frame, textvariable=self.annual_return_var).grid(
            row=1, column=1, sticky="ew", padx=10, pady=7
        )

        self.profile_blurb = tk.Label(
            assumptions_frame,
            text=(
                "TD-style basic savings keeps the model ultra-conservative; "
                "you can override the annual return assumption at any time."
            ),
            wraplength=320,
            justify="left",
            bg=APP_BG,
            fg=MUTED,
            font=self.base_font,
        )
        self.profile_blurb.grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 10)
        )

        action_frame = tk.Frame(parent, bg=APP_BG)
        action_frame.pack(fill="x", pady=(0, 10))
        ttk.Button(
            action_frame,
            text="Run Tuition Forecast",
            style="Accent.TButton",
            command=self.run_forecast,
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            action_frame,
            text="Export Forecast to Excel",
            style="Secondary.TButton",
            command=self.export_current_scenario,
        ).pack(fill="x")

        note_card = self._create_text_card(
            parent,
            "How the Forecast Works",
            (
                "The forecast blends a recency-weighted polynomial regression with recent growth rates from available tuition data.\n\n"
                "Totals are shown both in future nominal dollars and in 2025 CPI-adjusted dollars so you can compare future sticker price against present-day buying power."
            ),
        )
        note_card.pack(fill="x")

    def _build_planner_content(self, parent: tk.Widget) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        metrics_frame = tk.Frame(parent, bg=APP_BG)
        metrics_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        for index in range(4):
            metrics_frame.columnconfigure(index, weight=1)

        self.metric_labels: dict[str, tk.Label] = {}
        metric_specs = [
            ("Projected 4-Year Tuition Cost", "tuition_target"),
            ("Projected Savings by Start Date", "projected_savings"),
            ("Gap or Surplus at Start", "gap"),
            ("Monthly Savings Needed", "required_monthly"),
        ]
        for column, (title, key) in enumerate(metric_specs):
            card = self._create_metric_card(metrics_frame, title)
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 8, 0),
                pady=(0, 12),
            )
            self.metric_labels[key] = card.nametowidget(f"{card}.value")

        charts_frame = tk.Frame(parent, bg=APP_BG)
        charts_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)

        self.tuition_chart_frame = self._create_chart_card(
            charts_frame, "Historical Tuition and Forecasted Costs"
        )
        self.tuition_chart_frame.grid(
            row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12)
        )
        self.savings_chart_frame = self._create_chart_card(
            charts_frame, "Savings Growth Compared with Tuition Goal"
        )
        self.savings_chart_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 12))

        lower_frame = tk.Frame(parent, bg=APP_BG)
        lower_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        lower_frame.columnconfigure(0, weight=1)
        lower_frame.columnconfigure(1, weight=1)

        forecast_table_card = self._create_card(
            lower_frame, "Projected Tuition by Academic Year"
        )
        forecast_table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.forecast_tree = ttk.Treeview(
            forecast_table_card,
            columns=("year", "nominal", "real", "cumulative"),
            show="headings",
            height=6,
        )
        for heading, label, width in (
            ("year", "Academic Year", 110),
            ("nominal", "Nominal Cost", 150),
            ("real", "2025-Dollar Cost", 150),
            ("cumulative", "Running Nominal Total", 170),
        ):
            self.forecast_tree.heading(heading, text=label)
            self.forecast_tree.column(heading, width=width, anchor="center")
        self.forecast_tree.pack(fill="both", expand=True, padx=12, pady=12)

        recommendation_card = self._create_card(
            lower_frame, "Recommended Savings Actions"
        )
        recommendation_card.grid(row=0, column=1, sticky="nsew")
        self.recommendations_text = ScrolledText(
            recommendation_card,
            height=10,
            wrap="word",
            font=self.base_font,
            bd=0,
        )
        self.recommendations_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.recommendations_text.configure(state="disabled")

    def _build_spending_tab(self) -> None:
        canvas = tk.Canvas(
            self.spending_tab,
            bg=APP_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            self.spending_tab, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content = tk.Frame(canvas, bg=APP_BG)
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _resize_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_inner_width(event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        content.bind("<Configure>", _resize_scroll_region)
        canvas.bind("<Configure>", _fit_inner_width)
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )

        controls = ttk.LabelFrame(
            content,
            text="Import and Map Spending Data",
            style="Section.TLabelframe",
        )
        controls.pack(fill="x", padx=0, pady=(8, 12))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Spending file (CSV)").grid(
            row=0, column=0, sticky="w", padx=10, pady=7
        )
        ttk.Entry(controls, textvariable=self.spending_file_var).grid(
            row=0, column=1, sticky="ew", padx=10, pady=7
        )
        ttk.Button(controls, text="Browse", command=self.browse_spending_file).grid(
            row=0, column=2, padx=(0, 10), pady=7
        )
        ttk.Button(
            controls,
            text="Map CSV Columns",
            command=self.open_column_mapping_dialog,
        ).grid(row=0, column=3, padx=(0, 10), pady=7)

        ttk.Label(controls, text="Monthly take-home income (optional)").grid(
            row=1, column=0, sticky="w", padx=10, pady=7
        )
        ttk.Entry(controls, textvariable=self.monthly_income_var).grid(
            row=1, column=1, sticky="ew", padx=10, pady=7
        )
        ttk.Label(controls, text="Extra monthly savings goal (optional)").grid(
            row=2, column=0, sticky="w", padx=10, pady=7
        )
        ttk.Entry(controls, textvariable=self.target_extra_savings_var).grid(
            row=2, column=1, sticky="ew", padx=10, pady=7
        )
        ttk.Button(
            controls,
            text="Analyze Spending File",
            style="Accent.TButton",
            command=self.run_spending_analysis,
        ).grid(row=1, column=3, rowspan=2, padx=(0, 10), pady=7, sticky="ns")

        tk.Label(
            controls,
            textvariable=self.mapping_status_var,
            bg=APP_BG,
            fg=MUTED,
            font=self.base_font,
            justify="left",
            wraplength=820,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 10))

        spending_actions = tk.Frame(content, bg=APP_BG)
        spending_actions.pack(fill="x", pady=(0, 10))
        ttk.Button(
            spending_actions,
            text="Apply Suggested Monthly Cut to Savings Plan",
            style="Secondary.TButton",
            command=self.apply_suggested_cut,
        ).pack(side="left")

        metrics_frame = tk.Frame(content, bg=APP_BG)
        metrics_frame.pack(fill="x", pady=(0, 12))
        for index in range(4):
            metrics_frame.columnconfigure(index, weight=1)

        self.spending_metric_labels: dict[str, tk.Label] = {}
        metric_specs = [
            ("Average Monthly Spending", "monthly_average"),
            ("Average Non-Essential Spending", "nonessential_average"),
            ("Suggested Monthly Cut", "suggested_cut"),
            ("Flagged Transactions", "anomaly_count"),
        ]
        for column, (title, key) in enumerate(metric_specs):
            card = self._create_metric_card(metrics_frame, title)
            card.grid(
                row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0)
            )
            self.spending_metric_labels[key] = card.nametowidget(f"{card}.value")

        charts_row = tk.Frame(content, bg=APP_BG)
        charts_row.pack(fill="both", expand=True)
        charts_row.columnconfigure(0, weight=1)
        charts_row.columnconfigure(1, weight=1)
        self.spending_breakdown_frame = self._create_chart_card(
            charts_row, "Largest Spending Categories"
        )
        self.spending_breakdown_frame.grid(
            row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12)
        )
        self.spending_trend_frame = self._create_chart_card(
            charts_row, "Monthly Spending Over Time"
        )
        self.spending_trend_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 12))

        bottom = tk.Frame(content, bg=APP_BG)
        bottom.pack(fill="both", expand=True)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        anomalies_card = self._create_card(
            bottom, "Unusual or High-Impact Transactions"
        )
        anomalies_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.anomalies_tree = ttk.Treeview(
            anomalies_card,
            columns=("date", "category", "amount", "essentiality"),
            show="headings",
            height=8,
        )
        for heading, label, width in (
            ("date", "Date", 110),
            ("category", "Category", 160),
            ("amount", "Spending Amount", 130),
            ("essentiality", "Essential?", 120),
        ):
            self.anomalies_tree.heading(heading, text=label)
            self.anomalies_tree.column(heading, width=width, anchor="center")
        self.anomalies_tree.pack(fill="both", expand=True, padx=12, pady=12)

        spending_rec_card = self._create_card(
            bottom, "Recommended Tuition-Saving Actions"
        )
        spending_rec_card.grid(row=0, column=1, sticky="nsew")
        self.spending_text = ScrolledText(
            spending_rec_card,
            height=10,
            wrap="word",
            font=self.base_font,
            bd=0,
        )
        self.spending_text.pack(fill="both", expand=True, padx=12, pady=12)
        self.spending_text.configure(state="disabled")

    def _build_history_tab(self) -> None:
        card = self._create_card(self.history_tab, "Recent Saved Forecast Scenarios")
        card.pack(fill="both", expand=True, pady=(8, 0))
        self.history_tree = ttk.Treeview(
            card,
            columns=(
                "created",
                "name",
                "year",
                "monthly",
                "tuition",
                "savings",
                "gap",
                "profile",
            ),
            show="headings",
        )
        columns = (
            ("created", "Created", 150),
            ("name", "Scenario", 220),
            ("year", "Start Year", 90),
            ("monthly", "Monthly Save", 120),
            ("tuition", "4-Year Tuition", 130),
            ("savings", "Projected Savings", 130),
            ("gap", "Gap / Surplus", 120),
            ("profile", "Risk Profile", 180),
        )
        for heading, label, width in columns:
            self.history_tree.heading(heading, text=label)
            self.history_tree.column(heading, width=width, anchor="center")
        self.history_tree.pack(fill="both", expand=True, padx=12, pady=(12, 8))
        action_row = tk.Frame(card, bg=CARD_BG)
        action_row.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(
            action_row,
            text="Load Selected Scenario",
            command=self.load_selected_scenario,
        ).pack(side="left")
        ttk.Button(
            action_row,
            text="Clear All History",
            command=self.clear_history,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            action_row, text="Refresh Scenario History", command=self.refresh_history
        ).pack(side="right")

    def _sync_profile_return(self, *_args) -> None:
        profile = get_profile(self.risk_profile_var.get())
        self.annual_return_var.set(f"{profile.annual_return * 100:.2f}")
        self.profile_blurb.configure(text=profile.description)

    def _create_metric_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
            highlightthickness=1,
        )
        tk.Label(
            card,
            text=title,
            bg=CARD_BG,
            fg=MUTED,
            font=self.section_font,
        ).pack(anchor="w", padx=14, pady=(12, 6))
        value_label = tk.Label(
            card,
            name="value",
            text="--",
            bg=CARD_BG,
            fg=PRIMARY,
            font=self.metric_font,
        )
        value_label.pack(anchor="w", padx=14, pady=(0, 12))
        return card

    def _create_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
            highlightthickness=1,
        )
        tk.Label(
            card,
            text=title,
            bg=CARD_BG,
            fg=PRIMARY,
            font=self.card_title_font,
        ).pack(anchor="w", padx=12, pady=(10, 0))
        return card

    def _create_text_card(self, parent: tk.Widget, title: str, body: str) -> tk.Frame:
        card = self._create_card(parent, title)
        tk.Label(
            card,
            text=body,
            bg=CARD_BG,
            fg=TEXT,
            justify="left",
            wraplength=320,
            font=self.base_font,
        ).pack(anchor="w", padx=12, pady=(8, 12))
        return card

    def _create_chart_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = self._create_card(parent, title)
        inner = tk.Frame(card, name="body", bg="white")
        inner.pack(fill="both", expand=True, padx=12, pady=12)
        return card

    def open_column_mapping_dialog(self) -> bool:
        csv_path = Path(self.spending_file_var.get().strip())
        if not csv_path.exists():
            messagebox.showerror(
                "Missing file",
                "Select a spending CSV before opening the column-mapping dialog.",
            )
            return False

        dialog = ColumnMappingDialog(
            self,
            csv_path=csv_path,
            default_mapping=self.spending_column_mapping,
        )
        self.wait_window(dialog)
        if dialog.result:
            self.spending_column_mapping = dialog.result
            chosen = ", ".join(
                f"{field} -> {column}"
                for field, column in self.spending_column_mapping.items()
            )
            self.mapping_status_var.set(f"CSV mapping: manual override active ({chosen})")
            return True
        return False

    def run_forecast(self, save_to_history: bool = True) -> None:
        try:
            scenario_name = self.scenario_name_var.get().strip() or "Unnamed Scenario"
            current_balance = self._parse_float(self.current_balance_var.get())
            monthly_contribution = self._parse_float(
                self.monthly_contribution_var.get()
            )
            target_year = self._parse_int(self.target_year_var.get())
            target_month = min(12, max(1, self._parse_int(self.target_month_var.get())))
            degree_years = max(1, self._parse_int(self.degree_years_var.get()))
            annual_return = self._parse_float(self.annual_return_var.get()) / 100
            target_date = date(target_year, target_month, 1)
        except ValueError as error:
            messagebox.showerror("Invalid input", str(error))
            return

        tuition_table = self.forecaster.forecast_degree_cost(target_year, degree_years)
        goal_value = float(tuition_table["nominal_cost"].sum())
        goal_value_real = float(tuition_table["real_2025_cost"].sum())
        savings_schedule = future_value_schedule(
            start_balance=current_balance,
            monthly_contribution=monthly_contribution,
            annual_return=annual_return,
            start_date=date.today(),
            target_date=target_date,
        )
        projected_balance = float(
            savings_schedule["balance"].iloc[-1]
            if not savings_schedule.empty
            else current_balance
        )
        months = int(len(savings_schedule))
        required_monthly = float(
            required_monthly_contribution(
                goal_value, annual_return, months, current_balance
            )
        )
        gap = goal_value - projected_balance

        recommendations = build_savings_recommendations(
            goal_value=goal_value,
            projected_balance=projected_balance,
            required_monthly=required_monthly,
            actual_monthly=monthly_contribution,
            annual_return=annual_return,
        )
        profile = get_profile(self.risk_profile_var.get())
        recommendations.append(
            f"The current profile is '{profile.name}', which assumes {annual_return * 100:.2f}% annual growth."
        )
        recommendations.append(
            f"The inflation-adjusted 2025-dollar estimate for the degree is about ${goal_value_real:,.0f}."
        )
        if self.current_spending is not None:
            suggested_cut = float(self.current_spending.metrics["suggested_cut"])
            if gap > 0:
                coverage = min(100.0, suggested_cut / max(required_monthly, 1) * 100)
                recommendations.append(
                    f"Your latest spending analysis suggests roughly ${suggested_cut:,.0f} per month of cuts, covering about {coverage:.0f}% of the savings target."
                )

        summary = {
            "scenario_name": scenario_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "target_start_year": target_year,
            "degree_years": degree_years,
            "starting_balance": round(current_balance, 2),
            "monthly_contribution": round(monthly_contribution, 2),
            "annual_return": round(annual_return, 6),
            "risk_profile": profile.name,
            "forecast_total_nominal": round(goal_value, 2),
            "forecast_total_real": round(goal_value_real, 2),
            "projected_balance": round(projected_balance, 2),
            "shortfall": round(gap, 2),
            "spending_file": self.spending_file_var.get().strip() or None,
        }
        self.current_bundle = ForecastBundle(
            summary=summary,
            tuition_table=tuition_table,
            savings_schedule=savings_schedule,
            recommendations=recommendations,
        )

        self._update_forecast_metrics(summary, required_monthly)
        self._populate_forecast_table(tuition_table)
        self._set_text(self.recommendations_text, recommendations)
        self._draw_figure(
            "tuition",
            self.tuition_chart_frame,
            tuition_figure(self.tuition_history, tuition_table),
        )
        self._draw_figure(
            "savings",
            self.savings_chart_frame,
            savings_figure(savings_schedule, goal_value),
        )

        if save_to_history:
            self.repository.save_scenario(
                {**summary, "recommendations": " | ".join(recommendations)}
            )
            self.refresh_history()

    def run_spending_analysis(self) -> None:
        spending_path = Path(self.spending_file_var.get().strip())
        if not spending_path.exists():
            messagebox.showerror(
                "Unable to analyze spending",
                "Select a valid spending CSV before running the analysis.",
            )
            return

        try:
            monthly_income = self._parse_optional_float(self.monthly_income_var.get())
            target_extra = self._parse_optional_float(
                self.target_extra_savings_var.get()
            )
            spending_df = load_spending_history(
                spending_path,
                column_mapping=self.spending_column_mapping,
            )
        except ValueError as error:
            if "manual column mapping" in str(error).lower():
                should_map = messagebox.askyesno(
                    "Map columns?",
                    str(error)
                    + "\n\nWould you like to map the CSV columns manually now?",
                )
                if should_map and self.open_column_mapping_dialog():
                    self.run_spending_analysis()
                return
            messagebox.showerror("Unable to analyze spending", str(error))
            return
        except Exception as error:
            messagebox.showerror("Unable to analyze spending", str(error))
            return

        try:
            insights = analyze_spending(
                spending_df,
                monthly_income=monthly_income,
                target_extra_savings=target_extra,
            )
        except Exception as error:
            messagebox.showerror("Unable to analyze spending", str(error))
            return

        if self.spending_column_mapping is None:
            self.mapping_status_var.set(
                "CSV mapping: automatic detection succeeded for date, description, spending amount, and any available balance column."
            )

        self.current_spending = insights
        self._update_spending_metrics(insights.metrics)
        self._populate_anomalies(insights.anomalies)
        self._set_text(self.spending_text, insights.recommendations)
        self._draw_figure(
            "spending_breakdown",
            self.spending_breakdown_frame,
            spending_breakdown_figure(insights.category_summary),
        )
        self._draw_figure(
            "spending_trend",
            self.spending_trend_frame,
            monthly_spending_figure(insights.monthly_summary),
        )

        if self.current_bundle is not None:
            self.run_forecast(save_to_history=False)

    def apply_suggested_cut(self) -> None:
        if self.current_spending is None:
            messagebox.showinfo(
                "No analysis yet",
                "Run a spending analysis first so the app can estimate a realistic monthly cut.",
            )
            return
        current = self._parse_float(self.monthly_contribution_var.get())
        new_value = current + float(self.current_spending.metrics["suggested_cut"])
        self.monthly_contribution_var.set(f"{new_value:.2f}")
        self.run_forecast()

    def export_current_scenario(self) -> None:
        if self.current_bundle is None:
            messagebox.showinfo(
                "No forecast available", "Run a forecast before exporting."
            )
            return

        file_stem = self.current_bundle.summary["scenario_name"].replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = EXPORTS_DIR / f"{file_stem}_{timestamp}.xlsx"
        export_workbook(
            output_path=output_path,
            summary=self.current_bundle.summary,
            tuition_table=self.current_bundle.tuition_table,
            savings_table=self.current_bundle.savings_schedule,
            spending_summary=self.current_spending.metrics
            if self.current_spending
            else None,
        )
        messagebox.showinfo("Export complete", f"Scenario exported to:\n{output_path}")

    def refresh_history(self) -> None:
        self.history_item_ids = {}
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        history = self.repository.list_recent_scenarios()
        for row in history.itertuples(index=False):
            item_id = self.history_tree.insert(
                "",
                "end",
                values=(
                    row.created_at,
                    row.scenario_name,
                    row.target_start_year,
                    self._money(row.monthly_contribution),
                    self._money(row.forecast_total_nominal),
                    self._money(row.projected_balance),
                    self._money(row.shortfall),
                    row.risk_profile,
                ),
            )
            self.history_item_ids[item_id] = int(row.id)

    def load_selected_scenario(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo(
                "No scenario selected",
                "Select a saved scenario in the history table first.",
            )
            return

        scenario_id = self.history_item_ids.get(selected[0])
        if scenario_id is None:
            messagebox.showerror(
                "Unable to load scenario",
                "The selected history row could not be resolved.",
            )
            return

        scenario = self.repository.get_scenario(scenario_id)
        if scenario is None:
            messagebox.showerror(
                "Scenario not found",
                "That saved scenario no longer exists in the database.",
            )
            self.refresh_history()
            return

        self.scenario_name_var.set(str(scenario["scenario_name"]))
        self.current_balance_var.set(f"{float(scenario['starting_balance']):.2f}")
        self.monthly_contribution_var.set(
            f"{float(scenario['monthly_contribution']):.2f}"
        )
        self.target_year_var.set(str(int(scenario["target_start_year"])))
        self.degree_years_var.set(str(int(scenario["degree_years"])))
        self.risk_profile_var.set(str(scenario["risk_profile"]))
        saved_return_percent = float(scenario["annual_return"]) * 100
        self.annual_return_var.set(f"{saved_return_percent:.2f}")
        spending_file = scenario.get("spending_file")
        if spending_file:
            self.spending_file_var.set(str(spending_file))
        self._sync_profile_return()
        self.annual_return_var.set(f"{saved_return_percent:.2f}")
        self.run_forecast(save_to_history=False)
        self.focus_force()
        messagebox.showinfo(
            "Scenario loaded",
            "The selected scenario has been loaded onto the planner dashboard.",
        )

    def clear_history(self) -> None:
        should_clear = messagebox.askyesno(
            "Clear scenario history?",
            "This will permanently remove all saved scenarios from the history table.",
        )
        if not should_clear:
            return
        self.repository.clear_history()
        self.refresh_history()

    def browse_spending_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select spending CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=str(ROOT_DIR),
        )
        if path:
            self.spending_file_var.set(path)
            self.spending_column_mapping = None
            self.mapping_status_var.set(
                "CSV mapping: automatic detection enabled for the selected file"
            )

    def _update_forecast_metrics(
        self, summary: dict[str, object], required_monthly: float
    ) -> None:
        self.metric_labels["tuition_target"].configure(
            text=self._money(summary["forecast_total_nominal"])
        )
        self.metric_labels["projected_savings"].configure(
            text=self._money(summary["projected_balance"])
        )
        gap_value = float(summary["shortfall"])
        prefix = "Gap " if gap_value > 0 else "Surplus "
        self.metric_labels["gap"].configure(
            text=f"{prefix}{self._money(abs(gap_value))}"
        )
        self.metric_labels["required_monthly"].configure(text=self._money(required_monthly))

    def _update_spending_metrics(self, metrics: dict[str, float]) -> None:
        self.spending_metric_labels["monthly_average"].configure(
            text=self._money(metrics["monthly_average"])
        )
        self.spending_metric_labels["nonessential_average"].configure(
            text=self._money(metrics["nonessential_average"])
        )
        self.spending_metric_labels["suggested_cut"].configure(
            text=self._money(metrics["suggested_cut"])
        )
        self.spending_metric_labels["anomaly_count"].configure(
            text=str(metrics["anomaly_count"])
        )

    def _populate_forecast_table(self, tuition_table) -> None:
        for item in self.forecast_tree.get_children():
            self.forecast_tree.delete(item)
        for row in tuition_table.itertuples(index=False):
            self.forecast_tree.insert(
                "",
                "end",
                values=(
                    row.academic_year,
                    self._money(row.nominal_cost),
                    self._money(row.real_2025_cost),
                    self._money(row.cumulative_nominal),
                ),
            )

    def _populate_anomalies(self, anomalies) -> None:
        for item in self.anomalies_tree.get_children():
            self.anomalies_tree.delete(item)
        for row in anomalies.itertuples(index=False):
            self.anomalies_tree.insert(
                "",
                "end",
                values=(
                    row.date.strftime("%Y-%m-%d"),
                    row.category,
                    self._money(row.amount),
                    row.essentiality,
                ),
            )

    def _draw_figure(self, key: str, frame: tk.Widget, figure) -> None:
        existing = self.figure_canvases.get(key)
        if existing is not None:
            existing.get_tk_widget().destroy()
        host = frame.nametowidget(f"{frame}.body")
        canvas = FigureCanvasTkAgg(figure, master=host)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.figure_canvases[key] = canvas

    def _set_text(self, widget: ScrolledText, lines: list[str]) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", "\n\n".join(lines))
        widget.configure(state="disabled")

    @staticmethod
    def _money(value: object) -> str:
        return f"${float(value):,.0f}"

    @staticmethod
    def _parse_float(value: str) -> float:
        cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
        if not cleaned:
            raise ValueError("A required numeric input is empty.")
        return float(cleaned)

    @staticmethod
    def _parse_optional_float(value: str) -> float | None:
        cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
        if not cleaned:
            return None
        return float(cleaned)

    @staticmethod
    def _parse_int(value: str) -> int:
        return int(float(value.strip()))


def launch() -> None:
    app = TuitionPlannerApp()
    app.mainloop()
