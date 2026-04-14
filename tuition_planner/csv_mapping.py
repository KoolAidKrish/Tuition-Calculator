from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from tuition_planner.data_loader import load_spending_preview


APP_BG = "#F6F1E7"
CARD_BG = "#FFF9F0"
CARD_BORDER = "#D7C7AE"
PRIMARY = "#264653"
TEXT = "#2B2D42"
MUTED = "#6C757D"


class ColumnMappingDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        csv_path: Path,
        default_mapping: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Map Spending CSV Columns")
        self.configure(bg=APP_BG)
        self.geometry("980x650")
        self.minsize(840, 560)
        self.transient(parent)
        self.grab_set()
        self.result: dict[str, str] | None = None

        preview_df = load_spending_preview(csv_path)
        columns = list(preview_df.columns)
        self.mapping_vars: dict[str, tk.StringVar] = {}

        wrapper = tk.Frame(self, bg=APP_BG)
        wrapper.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(
            wrapper,
            text="Manual Spending CSV Mapping",
            bg=APP_BG,
            fg=PRIMARY,
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        tk.Label(
            wrapper,
            text=(
                "Match your bank-export columns to the fields the app needs. "
                "Required fields are date, description, and spending amount."
            ),
            bg=APP_BG,
            fg=MUTED,
            font=("Segoe UI", 10),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        form = tk.Frame(wrapper, bg=APP_BG)
        form.pack(fill="x", pady=(0, 12))
        form.columnconfigure(1, weight=1)

        mapping_fields = [
            ("date", "Transaction date"),
            ("description", "Description / merchant"),
            ("amount", "Spending amount"),
            ("balance", "Account balance (optional)"),
            ("category", "Category (optional)"),
        ]
        for row, (key, label) in enumerate(mapping_fields):
            tk.Label(
                form,
                text=label,
                bg=APP_BG,
                fg=TEXT,
                font=("Segoe UI Semibold", 10),
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            values = [""] + columns
            variable = tk.StringVar(value=(default_mapping or {}).get(key, ""))
            self.mapping_vars[key] = variable
            ttk.Combobox(
                form,
                textvariable=variable,
                values=values,
                state="readonly",
            ).grid(row=row, column=1, sticky="ew", pady=6)

        preview_card = tk.Frame(
            wrapper,
            bg=CARD_BG,
            bd=1,
            relief="solid",
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
            highlightthickness=1,
        )
        preview_card.pack(fill="both", expand=True)
        tk.Label(
            preview_card,
            text="CSV Preview",
            bg=CARD_BG,
            fg=PRIMARY,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", padx=12, pady=(10, 0))

        preview_frame = tk.Frame(preview_card, bg=CARD_BG)
        preview_frame.pack(fill="both", expand=True, padx=12, pady=12)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(preview_frame, columns=columns, show="headings", height=12)
        for column in columns:
            tree.heading(column, text=str(column))
            tree.column(column, width=140, anchor="center")
        for row in preview_df.fillna("").itertuples(index=False):
            tree.insert("", "end", values=row)
        y_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(
            preview_frame, orient="horizontal", command=tree.xview
        )
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        button_row = tk.Frame(wrapper, bg=APP_BG)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(button_row, text="Use Mapping", command=self._save).pack(
            side="right", padx=(0, 8)
        )

    def _save(self) -> None:
        required = ["date", "description", "amount"]
        missing = [field for field in required if not self.mapping_vars[field].get()]
        if missing:
            messagebox.showerror(
                "Missing fields",
                "Please assign the required fields: "
                + ", ".join(field.title() for field in missing),
                parent=self,
            )
            return
        self.result = {
            key: variable.get()
            for key, variable in self.mapping_vars.items()
            if variable.get()
        }
        self.destroy()
