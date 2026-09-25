from pathlib import Path
import math
import pandas as pd
import numpy as np


class ExportAgent:
    name = "Export Agent"

    @staticmethod
    def _serializable_valuation(valuation):
        return {k: v for k, v in valuation.items() if k != "UFCF"}

    # Backward-compatible raw export
    def export_excel(self, outpath, result):
        outpath = Path(outpath)
        ticker = result["meta"]["Ticker"]
        with pd.ExcelWriter(outpath, engine="xlsxwriter") as w:
            result["historical"].to_excel(w, sheet_name="Historical")
            for name, df in result["forecasts"].items():
                df.to_excel(w, sheet_name=f"3Stmt_{name}")
            result["kpis"].to_excel(w, sheet_name="KPIs")
            pd.DataFrame([result["assumptions"]]).to_excel(w, sheet_name="Assumptions", index=False)
            pd.DataFrame([self._serializable_valuation(result["valuation"])]).to_excel(w, sheet_name="DCF", index=False)
            result["sensitivity"].to_excel(w, sheet_name="DCF_Sensitivity", index=False)
            pd.DataFrame([result["reverse_dcf"]]).to_excel(w, sheet_name="Reverse_DCF", index=False)
            pd.DataFrame([result["monte_carlo"]]).to_excel(w, sheet_name="Monte_Carlo", index=False)
            if result["comps"] is not None and not result["comps"].empty:
                result["comps"].to_excel(w, sheet_name="Trading_Comps", index=False)
            if result["audit"]:
                pd.DataFrame(result["audit"]).to_excel(w, sheet_name="Model_Checks", index=False)
            for name, df in result.get("consensus", {}).items():
                safe = ("Consensus_" + name)[:31]
                df.to_excel(w, sheet_name=safe)
            pd.DataFrame([result["meta"]]).to_excel(w, sheet_name="Audit", index=False)
            pd.DataFrame({"Ticker": [ticker], "Note": ["This workbook contains actuals, model forecasts, valuation outputs and audit checks. Verify critical decisions against primary filings."]}).to_excel(w, sheet_name="README", index=False)
        return str(outpath)

    def export_linked_financial_model(self, outpath, result):
        """Create a presentation-ready, formula-linked financial model workbook.

        The model is expressed in currency crores (1 crore = 10 million). Historical values and market inputs are
        hardcoded source data (blue font); forecasts and valuation are Excel formulas.
        """
        import xlsxwriter

        outpath = Path(outpath)
        outpath.parent.mkdir(parents=True, exist_ok=True)

        meta = result["meta"]
        info = result["data"].info or {}
        hist = result["historical"].copy()
        assumptions = dict(result["assumptions"])
        forecasts = result["forecasts"]
        comps = result.get("comps")
        audit = result.get("audit", [])
        ticker = meta.get("Ticker", "Company")
        company = meta.get("Company") or ticker
        currency = meta.get("Currency") or "Currency"
        source = meta.get("Source") or "Yahoo Finance via yfinance"

        # Convert model amounts to crores for Indian-style readable workbook.
        # 1 crore = 10,000,000 units of the underlying currency.
        scale = 10_000_000.0
        currency_symbol = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}.get(str(currency).upper(), str(currency))
        unit_label = f"{currency_symbol} Cr"
        hist_mm = hist / scale
        hist_cols = list(hist_mm.columns)
        forecast_cols = list(forecasts["Base"].columns)
        all_cols = hist_cols + forecast_cols
        n_hist = len(hist_cols)
        n_fc = len(forecast_cols)

        wb = xlsxwriter.Workbook(str(outpath))
        wb.set_properties({
            "title": f"{company} Financial Model",
            "subject": "Formula-linked 3-statement financial model and valuation",
            "author": "FinModel AI",
            "comments": "Generated from source actuals and editable model assumptions.",
        })

        # Palette / formats
        dark = "#0B1F33"
        navy = "#17365D"
        light_blue = "#D9EAF7"
        light_gray = "#E7E6E6"
        green_fill = "#E2F0D9"
        yellow = "#FFF2CC"
        red_fill = "#FCE4D6"
        white = "#FFFFFF"
        black = "#000000"
        blue = "#0000FF"
        green = "#008000"
        red = "#FF0000"

        fmt_title = wb.add_format({"bold": True, "font_size": 20, "font_color": white, "bg_color": dark, "align": "left", "valign": "vcenter"})
        fmt_subtitle = wb.add_format({"font_size": 10, "font_color": "#D9E2F3", "bg_color": dark})
        fmt_section = wb.add_format({"bold": True, "font_color": white, "bg_color": navy, "align": "left", "border": 0})
        fmt_header = wb.add_format({"bold": True, "font_color": white, "bg_color": navy, "align": "right", "bottom": 1})
        fmt_header_left = wb.add_format({"bold": True, "font_color": white, "bg_color": navy, "align": "left", "bottom": 1})
        fmt_label = wb.add_format({"font_color": black, "align": "left"})
        fmt_sub_label = wb.add_format({"font_color": black, "align": "left", "indent": 1})
        fmt_input = wb.add_format({"font_color": blue, "num_format": "0.0%;[Red](0.0%);-", "bg_color": yellow})
        fmt_input_num = wb.add_format({"font_color": blue, "num_format": "0.0;[Red](0.0);-", "bg_color": yellow})
        fmt_input_money = wb.add_format({"font_color": blue, "num_format": "#,##0.0;[Red](#,##0.0);-", "bg_color": yellow})
        fmt_formula = wb.add_format({"font_color": black, "num_format": "#,##0.0;[Red](#,##0.0);-", "align": "right"})
        fmt_link = wb.add_format({"font_color": green, "num_format": "#,##0.0;[Red](#,##0.0);-", "align": "right"})
        fmt_hardcode = wb.add_format({"font_color": blue, "num_format": "#,##0.0;[Red](#,##0.0);-", "align": "right"})
        fmt_percent = wb.add_format({"font_color": black, "num_format": "0.0%;[Red](0.0%);-", "align": "right"})
        fmt_percent_link = wb.add_format({"font_color": green, "num_format": "0.0%;[Red](0.0%);-", "align": "right"})
        fmt_percent_input = wb.add_format({"font_color": blue, "num_format": "0.0%;[Red](0.0%);-", "bg_color": yellow, "align": "right"})
        fmt_multiple = wb.add_format({"font_color": black, "num_format": "0.0x;[Red](0.0x);-", "align": "right"})
        fmt_price = wb.add_format({"font_color": black, "num_format": "0.00;[Red](0.00);-", "align": "right"})
        fmt_price_input = wb.add_format({"font_color": blue, "num_format": "0.00;[Red](0.00);-", "bg_color": yellow})
        fmt_total = wb.add_format({"bold": True, "font_color": black, "num_format": "#,##0.0;[Red](#,##0.0);-", "top": 1, "align": "right"})
        fmt_total_link = wb.add_format({"bold": True, "font_color": green, "num_format": "#,##0.0;[Red](#,##0.0);-", "top": 1, "align": "right"})
        fmt_total_label = wb.add_format({"bold": True, "top": 1})
        fmt_check_ok = wb.add_format({"font_color": "#006100", "bg_color": green_fill, "num_format": "0.0;[Red](0.0);-"})
        fmt_check_bad = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE", "num_format": "0.0;[Red](0.0);-"})
        fmt_note = wb.add_format({"font_color": "#666666", "italic": True, "font_size": 9, "text_wrap": True})
        fmt_text = wb.add_format({"font_color": black})
        fmt_source = wb.add_format({"font_color": blue, "underline": True})
        fmt_kpi = wb.add_format({"bold": True, "font_size": 12, "font_color": white, "bg_color": navy, "align": "center", "valign": "vcenter", "border": 1})
        fmt_kpi_value = wb.add_format({"bold": True, "font_size": 15, "num_format": "0.00;[Red](0.00);-", "align": "center", "valign": "vcenter", "border": 1})
        fmt_kpi_pct = wb.add_format({"bold": True, "font_size": 15, "num_format": "0.0%;[Red](0.0%);-", "align": "center", "valign": "vcenter", "border": 1})
        # Standard model period headers and presentation dashboard card formats.
        fmt_header_actual = wb.add_format({"bold": True, "font_color": "#404040", "bg_color": "#D9E1F2", "align": "right", "bottom": 1})
        fmt_header_forecast = wb.add_format({"bold": True, "font_color": white, "bg_color": "#4472C4", "align": "right", "bottom": 1})
        fmt_dash_section = wb.add_format({"bold": True, "font_size": 11, "font_color": white, "bg_color": "#1F4E78", "align": "left", "valign": "vcenter"})
        dash_cards = [
            ("#1F4E78", "#D9EAF7"),  # blue
            ("#2F75B5", "#DDEBF7"),  # light blue
            ("#548235", "#E2F0D9"),  # green
            ("#BF8F00", "#FFF2CC"),  # gold
            ("#7030A0", "#E4DFEC"),  # purple
            ("#008C95", "#DDEBF7"),  # teal
        ]
        fmt_dash_labels = [wb.add_format({"bold": True, "font_size": 10, "font_color": white, "bg_color": c, "align": "center", "valign": "vcenter", "border": 1, "border_color": c}) for c, _ in dash_cards]
        fmt_dash_values = [wb.add_format({"bold": True, "font_size": 16, "font_color": "#1F1F1F", "bg_color": f, "align": "center", "valign": "vcenter", "border": 1, "border_color": c, "num_format": "0.00;[Red](0.00);-"}) for c, f in dash_cards]
        fmt_dash_values_pct = [wb.add_format({"bold": True, "font_size": 16, "font_color": "#1F1F1F", "bg_color": f, "align": "center", "valign": "vcenter", "border": 1, "border_color": c, "num_format": "0.0%;[Red](0.0%);-"}) for c, f in dash_cards]

        def setup(ws, freeze=(4, 1)):
            ws.hide_gridlines(2)
            ws.set_zoom(90)
            ws.set_column(0, 0, 30)
            ws.set_column(1, 20, 13)
            # Familiar investment-banking workbook organization through tab colors.
            if ws.name in ["Cover", "Dashboard"]:
                ws.set_tab_color("#1F4E78")
            elif ws.name == "Assumptions":
                ws.set_tab_color("#FFC000")
            elif ws.name.startswith("Historical"):
                ws.set_tab_color("#A5A5A5")
            elif ws.name.startswith("Forecast") or ws.name in ["Revenue Build", "Working Capital", "Capex & D&A", "Debt Schedule"]:
                ws.set_tab_color("#4472C4")
            elif ws.name in ["DCF", "DCF Sensitivity", "Scenario Analysis", "KPIs"]:
                ws.set_tab_color("#70AD47")
            elif ws.name in ["Model Checks", "Sources"]:
                ws.set_tab_color("#ED7D31")
            if freeze:
                ws.freeze_panes(*freeze)

        def title(ws, subtitle):
            ws.set_row(0, 28)
            ws.merge_range(0, 0, 0, max(8, len(all_cols) + 1), f"{company} ({ticker}) — Financial Model", fmt_title)
            ws.merge_range(1, 0, 1, max(8, len(all_cols) + 1), subtitle, fmt_subtitle)

        def section(ws, row, text, last_col):
            ws.merge_range(row, 0, row, last_col, text, fmt_section)
            return row + 1

        def xl_col(col_idx):
            # 0-based index -> Excel col string
            s = ""
            x = col_idx + 1
            while x:
                x, rem = divmod(x - 1, 26)
                s = chr(65 + rem) + s
            return s

        def quote_sheet(name):
            return "'" + name.replace("'", "''") + "'"

        source_comment = f"Source: {source}\nFetched: {meta.get('Data Timestamp UTC')}\nActual/source value; verify against primary company filings for material decisions."

        # ---------------- Cover ----------------
        ws = wb.add_worksheet("Cover")
        setup(ws, None)
        ws.set_column(0, 0, 3)
        ws.set_column(1, 1, 26)
        ws.set_column(2, 5, 22)
        ws.merge_range("B2:F3", "FinModel AI — Complete Financial Model", fmt_title)
        ws.merge_range("B4:F4", f"{company} ({ticker}) | {currency} | Generated from actuals + editable formula-driven forecasts | Monetary values shown in crores", fmt_subtitle)
        cover_items = [
            ("Company", company), ("Ticker", ticker), ("Exchange", meta.get("Exchange")),
            ("Sector", meta.get("Sector")), ("Industry", meta.get("Industry")),
            ("Currency", currency), ("Data Source", source), ("Fetched", meta.get("Data Timestamp UTC")),
            ("Forecast Years", meta.get("Forecast Years")),
        ]
        r = 6
        for label, value in cover_items:
            ws.write(r, 1, label, fmt_header_left)
            ws.write(r, 2, "" if value is None else value, fmt_text)
            r += 1
        r += 1
        ws.write(r, 1, "Workbook Map", fmt_section)
        r += 1
        map_rows = [
            ("Assumptions", "Editable scenario selector and operating / valuation inputs"),
            ("Historical IS / BS / CF", "Source actuals in currency crores"),
            ("Revenue Build", "Formula-driven revenue forecast"),
            ("Working Capital", "DSO / DIO / DPO schedules"),
            ("Capex & D&A", "Capex, depreciation and PP&E roll-forward"),
            ("Debt Schedule", "Debt repayment, average debt and interest"),
            ("Forecast IS / BS / CF", "Integrated formula-linked 3-statement model"),
            ("DCF", "Unlevered FCF, WACC, terminal value and implied price"),
            ("Comps", "Trading comparable companies where supplied"),
            ("Sensitivity", "WACC / terminal-growth implied-price matrix"),
            ("Scenario Analysis", "Bear / Base / Bull outputs"),
            ("KPIs", "Margins, growth, leverage and returns"),
            ("Model Checks", "Balance sheet and cash-flow integrity checks"),
            ("Dashboard", "Linked charts and valuation summary for screenshots"),
        ]
        for name, desc in map_rows:
            ws.write(r, 1, name, fmt_label)
            ws.write(r, 2, desc, fmt_note)
            r += 1
        ws.merge_range(r + 1, 1, r + 3, 5,
                       "Color convention: BLUE = hardcoded/editable inputs; GREEN = links from other worksheets; BLACK = formulas; YELLOW = key assumptions. This model is a decision-support tool, not a guarantee of investment outcomes.",
                       fmt_note)

        # ---------------- Assumptions ----------------
        ws = wb.add_worksheet("Assumptions")
        setup(ws)
        title(ws, "Editable operating and valuation assumptions. Change yellow/blue cells; formulas throughout the workbook recalculate.")
        ws.write("A4", "Selected Scenario", fmt_header_left)
        ws.write("B4", "Base", fmt_input_num)
        ws.data_validation("B4", {"validate": "list", "source": ["Bear", "Base", "Bull"]})
        ws.write_comment("B4", "Select Bear, Base or Bull. Forecast sheets use the selected scenario through formula links.")

        assumption_rows = [
            ("Revenue Growth", "revenue_growth", "pct"),
            ("Gross Margin", "gross_margin", "pct"),
            ("EBITDA Margin", "ebitda_margin", "pct"),
            ("D&A % Revenue", "da_pct_revenue", "pct"),
            ("Capex % Revenue", "capex_pct_revenue", "pct"),
            ("Tax Rate", "tax_rate", "pct"),
            ("DSO", "dso", "num"),
            ("DIO", "dio", "num"),
            ("DPO", "dpo", "num"),
            ("Interest Rate", "interest_rate", "pct"),
            ("Debt Repayment %", "debt_repayment_pct", "pct"),
            ("Dividend Payout", "dividend_payout", "pct"),
            ("Terminal Growth", "terminal_growth", "pct"),
            ("Risk-free Rate", "risk_free_rate", "pct"),
            ("Equity Risk Premium", "equity_risk_premium", "pct"),
        ]
        row0 = 6
        ws.write_row(row0 - 1, 0, ["Operating Assumption", "Base", "Bear", "Bull", "Selected"], fmt_header_left)
        assumption_row_map = {}
        for i, (label, key, kind) in enumerate(assumption_rows):
            rr = row0 + i
            assumption_row_map[key] = rr + 1  # Excel row
            base_val = float(assumptions.get(key, 0) or 0)
            # Scenario deltas match ScheduleAgent logic for key growth/margin items; others remain equal.
            bear = base_val
            bull = base_val
            if key == "revenue_growth":
                bear, bull = base_val - 0.03, base_val + 0.03
            elif key == "ebitda_margin":
                bear, bull = base_val - 0.02, base_val + 0.02
            elif key == "gross_margin":
                bear, bull = base_val - 0.01, base_val + 0.01
            ws.write(rr, 0, label, fmt_label)
            in_fmt = fmt_percent_input if kind == "pct" else fmt_input_num
            ws.write_number(rr, 1, base_val, in_fmt)
            ws.write_number(rr, 2, bear, in_fmt)
            ws.write_number(rr, 3, bull, in_fmt)
            ws.write_formula(rr, 4, f'=IF($B$4="Bear",C{rr+1},IF($B$4="Bull",D{rr+1},B{rr+1}))', fmt_formula if kind == "num" else fmt_percent)
            ws.write_comment(rr, 1, f"Derived from historical actuals by FinModel AI. Source actuals: {source}. Editable model assumption.")
        # Market / valuation inputs
        mr = row0 + len(assumption_rows) + 2
        ws.merge_range(mr, 0, mr, 4, "Market / Valuation Inputs", fmt_section)
        market_rows = [
            ("Beta", float(info.get("beta") or 1.0), "num"),
            ("Current Share Price", float(info.get("currentPrice") or info.get("regularMarketPrice") or 0), "price"),
            ("Shares Outstanding (Cr)", float(info.get("sharesOutstanding") or 0) / scale, "money"),
            ("Market Cap (Cr)", float(info.get("marketCap") or 0) / scale, "money"),
            ("WACC Override", float(result["valuation"].get("WACC") or 0.10), "pct"),
        ]
        market_row_map = {}
        for j, (label, value, kind) in enumerate(market_rows, start=1):
            rr = mr + j
            market_row_map[label] = rr + 1
            ws.write(rr, 0, label, fmt_label)
            f = fmt_percent_input if kind == "pct" else (fmt_price_input if kind == "price" else fmt_input_money)
            ws.write_number(rr, 1, value, f)
            ws.write_comment(rr, 1, source_comment if label != "WACC Override" else "Model WACC input. Change if you want to override the agent-derived WACC.")
        ws.set_column(0, 0, 28)
        ws.set_column(1, 4, 15)

        # helper refs
        A = {key: f"Assumptions!$E${row}" for key, row in assumption_row_map.items()}
        M = {label: f"Assumptions!$B${row}" for label, row in market_row_map.items()}

        # ---------------- Historical statements ----------------
        is_rows = ["Revenue", "Gross Profit", "EBITDA", "D&A", "EBIT", "Interest Expense", "Pretax Income", "Tax", "Net Income"]
        bs_rows = ["Cash", "Accounts Receivable", "Inventory", "Current Assets", "Accounts Payable", "Current Liabilities", "Net PPE", "Total Assets", "Total Debt", "Equity"]
        cf_rows = ["CFO", "Capex", "Dividends"]
        hist_sheet_rows = {}

        for sheet_name, rows, subtitle in [
            ("Historical IS", is_rows, "Historical income statement actuals"),
            ("Historical BS", bs_rows, "Historical balance sheet actuals"),
            ("Historical CF", cf_rows, "Historical cash flow actuals"),
        ]:
            ws = wb.add_worksheet(sheet_name)
            setup(ws)
            title(ws, f"{subtitle}. Units: {unit_label}. Blue font = source actuals.")
            ws.write(3, 0, f"{sheet_name} ({unit_label})", fmt_header_left)
            for j, p in enumerate(hist_cols, start=1):
                ws.write(3, j, p, fmt_header_actual)
            row_map = {}
            rr = 4
            for item in rows:
                row_map[item] = rr + 1
                ws.write(rr, 0, item, fmt_label)
                for j, p in enumerate(hist_cols, start=1):
                    val = float(hist_mm.loc[item, p]) if item in hist_mm.index else 0.0
                    ws.write_number(rr, j, val, fmt_hardcode)
                    ws.write_comment(rr, j, source_comment)
                rr += 1
            hist_sheet_rows[sheet_name] = row_map
            ws.autofilter(3, 0, rr - 1, len(hist_cols))

        # Historical references to final actual year
        last_hist_col_idx = n_hist  # because A labels, B=hist1
        last_hist_col_letter = xl_col(last_hist_col_idx)
        def href(sheet, item):
            row = hist_sheet_rows[sheet][item]
            return f"{quote_sheet(sheet)}!${last_hist_col_letter}${row}"

        # ---------------- Revenue Build ----------------
        ws = wb.add_worksheet("Revenue Build")
        setup(ws)
        title(ws, f"Revenue forecast build. Units: {unit_label}.")
        ws.write(3, 0, "Revenue Build", fmt_header_left)
        for j, p in enumerate(all_cols, start=1):
            ws.write(3, j, p, fmt_header_actual if j <= n_hist else fmt_header_forecast)
        ws.write(4, 0, "Revenue", fmt_label)
        ws.write(5, 0, "% Growth", fmt_sub_label)
        for j, p in enumerate(hist_cols, start=1):
            ws.write_formula(4, j, f"={quote_sheet('Historical IS')}!{xl_col(j)}5", fmt_link)
            if j == 1:
                ws.write_blank(5, j, None, fmt_percent)
            else:
                ws.write_formula(5, j, f"=IFERROR({xl_col(j)}5/{xl_col(j-1)}5-1,0)", fmt_percent)
        for k, p in enumerate(forecast_cols, start=1):
            j = n_hist + k
            prev = xl_col(j - 1)
            col = xl_col(j)
            ws.write_formula(4, j, f"={prev}5*(1+{A['revenue_growth']})", fmt_formula)
            ws.write_formula(5, j, f"={A['revenue_growth']}", fmt_percent_link)

        # ---------------- Working Capital ----------------
        ws = wb.add_worksheet("Working Capital")
        setup(ws)
        title(ws, f"Working capital schedule using DSO / DIO / DPO. Units: {unit_label}.")
        ws.write(3, 0, "Working Capital Schedule", fmt_header_left)
        for j, p in enumerate(all_cols, start=1): ws.write(3, j, p, fmt_header_actual if j <= n_hist else fmt_header_forecast)
        wc_rows = ["Revenue", "COGS", "Accounts Receivable", "DSO", "Inventory", "DIO", "Accounts Payable", "DPO", "Net Working Capital", "Change in NWC"]
        wc_map = {name: 5 + i for i, name in enumerate(wc_rows)}  # Excel rows
        for i, name in enumerate(wc_rows, start=4): ws.write(i, 0, name, fmt_sub_label if name in ["DSO", "DIO", "DPO"] else fmt_label)
        # historical
        for j, p in enumerate(hist_cols, start=1):
            c = xl_col(j)
            ws.write_formula(wc_map["Revenue"]-1, j, f"={quote_sheet('Historical IS')}!{c}5", fmt_link)
            ws.write_formula(wc_map["COGS"]-1, j, f"={quote_sheet('Historical IS')}!{c}5-{quote_sheet('Historical IS')}!{c}6", fmt_link)
            ws.write_formula(wc_map["Accounts Receivable"]-1, j, f"={quote_sheet('Historical BS')}!{c}6", fmt_link)
            ws.write_formula(wc_map["DSO"]-1, j, f"=IFERROR({c}{wc_map['Accounts Receivable']}/{c}{wc_map['Revenue']}*365,0)", fmt_formula)
            ws.write_formula(wc_map["Inventory"]-1, j, f"={quote_sheet('Historical BS')}!{c}7", fmt_link)
            ws.write_formula(wc_map["DIO"]-1, j, f"=IFERROR({c}{wc_map['Inventory']}/{c}{wc_map['COGS']}*365,0)", fmt_formula)
            ws.write_formula(wc_map["Accounts Payable"]-1, j, f"={quote_sheet('Historical BS')}!{c}9", fmt_link)
            ws.write_formula(wc_map["DPO"]-1, j, f"=IFERROR({c}{wc_map['Accounts Payable']}/{c}{wc_map['COGS']}*365,0)", fmt_formula)
            ws.write_formula(wc_map["Net Working Capital"]-1, j, f"={c}{wc_map['Accounts Receivable']}+{c}{wc_map['Inventory']}-{c}{wc_map['Accounts Payable']}", fmt_formula)
            if j == 1:
                ws.write_blank(wc_map["Change in NWC"]-1, j, None, fmt_formula)
            else:
                ws.write_formula(wc_map["Change in NWC"]-1, j, f"={c}{wc_map['Net Working Capital']}-{xl_col(j-1)}{wc_map['Net Working Capital']}", fmt_formula)
        # forecast
        for k, p in enumerate(forecast_cols, start=1):
            j = n_hist + k; c = xl_col(j)
            ws.write_formula(wc_map["Revenue"]-1, j, f"={quote_sheet('Revenue Build')}!{c}5", fmt_link)
            # COGS from forecast IS gross margin formula can be independently derived
            ws.write_formula(wc_map["COGS"]-1, j, f"={c}{wc_map['Revenue']}*(1-{A['gross_margin']})", fmt_formula)
            ws.write_formula(wc_map["Accounts Receivable"]-1, j, f"={c}{wc_map['Revenue']}*{A['dso']}/365", fmt_formula)
            ws.write_formula(wc_map["DSO"]-1, j, f"={A['dso']}", fmt_link)
            ws.write_formula(wc_map["Inventory"]-1, j, f"={c}{wc_map['COGS']}*{A['dio']}/365", fmt_formula)
            ws.write_formula(wc_map["DIO"]-1, j, f"={A['dio']}", fmt_link)
            ws.write_formula(wc_map["Accounts Payable"]-1, j, f"={c}{wc_map['COGS']}*{A['dpo']}/365", fmt_formula)
            ws.write_formula(wc_map["DPO"]-1, j, f"={A['dpo']}", fmt_link)
            ws.write_formula(wc_map["Net Working Capital"]-1, j, f"={c}{wc_map['Accounts Receivable']}+{c}{wc_map['Inventory']}-{c}{wc_map['Accounts Payable']}", fmt_formula)
            ws.write_formula(wc_map["Change in NWC"]-1, j, f"={c}{wc_map['Net Working Capital']}-{xl_col(j-1)}{wc_map['Net Working Capital']}", fmt_formula)

        # ---------------- Capex & D&A ----------------
        ws = wb.add_worksheet("Capex & D&A")
        setup(ws)
        title(ws, f"Capex, depreciation and net PP&E roll-forward. Units: {unit_label}.")
        ws.write(3, 0, "Capex & D&A Schedule", fmt_header_left)
        for j, p in enumerate(all_cols, start=1): ws.write(3, j, p, fmt_header_actual if j <= n_hist else fmt_header_forecast)
        cap_rows = ["Revenue", "Capex", "Capex % Revenue", "D&A", "D&A % Revenue", "Beginning Net PPE", "Ending Net PPE"]
        cap_map = {name: 5 + i for i, name in enumerate(cap_rows)}
        for i, name in enumerate(cap_rows, start=4): ws.write(i, 0, name, fmt_sub_label if "%" in name else fmt_label)
        for j, p in enumerate(hist_cols, start=1):
            c=xl_col(j)
            ws.write_formula(cap_map["Revenue"]-1,j,f"={quote_sheet('Historical IS')}!{c}5",fmt_link)
            ws.write_formula(cap_map["Capex"]-1,j,f"=-{quote_sheet('Historical CF')}!{c}6",fmt_link)
            ws.write_formula(cap_map["Capex % Revenue"]-1,j,f"=IFERROR({c}{cap_map['Capex']}/{c}{cap_map['Revenue']},0)",fmt_percent)
            ws.write_formula(cap_map["D&A"]-1,j,f"={quote_sheet('Historical IS')}!{c}8",fmt_link)
            ws.write_formula(cap_map["D&A % Revenue"]-1,j,f"=IFERROR({c}{cap_map['D&A']}/{c}{cap_map['Revenue']},0)",fmt_percent)
            if j == 1:
                ws.write_blank(cap_map["Beginning Net PPE"]-1,j,None,fmt_formula)
            else:
                ws.write_formula(cap_map["Beginning Net PPE"]-1,j,f"={xl_col(j-1)}{cap_map['Ending Net PPE']}",fmt_formula)
            ws.write_formula(cap_map["Ending Net PPE"]-1,j,f"={quote_sheet('Historical BS')}!{c}11",fmt_link)
        for k,p in enumerate(forecast_cols,start=1):
            j=n_hist+k;c=xl_col(j)
            ws.write_formula(cap_map["Revenue"]-1,j,f"={quote_sheet('Revenue Build')}!{c}5",fmt_link)
            ws.write_formula(cap_map["Capex"]-1,j,f"={c}{cap_map['Revenue']}*{A['capex_pct_revenue']}",fmt_formula)
            ws.write_formula(cap_map["Capex % Revenue"]-1,j,f"={A['capex_pct_revenue']}",fmt_percent_link)
            ws.write_formula(cap_map["D&A"]-1,j,f"={c}{cap_map['Revenue']}*{A['da_pct_revenue']}",fmt_formula)
            ws.write_formula(cap_map["D&A % Revenue"]-1,j,f"={A['da_pct_revenue']}",fmt_percent_link)
            ws.write_formula(cap_map["Beginning Net PPE"]-1,j,f"={xl_col(j-1)}{cap_map['Ending Net PPE']}",fmt_formula)
            ws.write_formula(cap_map["Ending Net PPE"]-1,j,f"={c}{cap_map['Beginning Net PPE']}+{c}{cap_map['Capex']}-{c}{cap_map['D&A']}",fmt_formula)

        # ---------------- Debt Schedule ----------------
        ws = wb.add_worksheet("Debt Schedule")
        setup(ws)
        title(ws, f"Debt and interest schedule. Units: {unit_label}.")
        ws.write(3, 0, "Debt Schedule", fmt_header_left)
        for j,p in enumerate(all_cols,start=1): ws.write(3,j,p,fmt_header)
        debt_rows=["Beginning Debt","Scheduled Repayment","Debt Draw","Ending Debt","Average Debt","Interest Rate","Interest Expense"]
        debt_map={name:5+i for i,name in enumerate(debt_rows)}
        for i,name in enumerate(debt_rows,start=4): ws.write(i,0,name,fmt_sub_label if name=="Interest Rate" else fmt_label)
        for j,p in enumerate(hist_cols,start=1):
            c=xl_col(j)
            if j==1: ws.write_blank(debt_map["Beginning Debt"]-1,j,None,fmt_formula)
            else: ws.write_formula(debt_map["Beginning Debt"]-1,j,f"={xl_col(j-1)}{debt_map['Ending Debt']}",fmt_formula)
            ws.write_blank(debt_map["Scheduled Repayment"]-1,j,None,fmt_formula)
            ws.write_blank(debt_map["Debt Draw"]-1,j,None,fmt_formula)
            ws.write_formula(debt_map["Ending Debt"]-1,j,f"={quote_sheet('Historical BS')}!{c}13",fmt_link)
            ws.write_formula(debt_map["Average Debt"]-1,j,f"={c}{debt_map['Ending Debt']}",fmt_formula)
            ws.write_formula(debt_map["Interest Rate"]-1,j,f"=IFERROR({quote_sheet('Historical IS')}!{c}10/{c}{debt_map['Average Debt']},0)",fmt_percent)
            ws.write_formula(debt_map["Interest Expense"]-1,j,f"={quote_sheet('Historical IS')}!{c}10",fmt_link)
        for k,p in enumerate(forecast_cols,start=1):
            j=n_hist+k;c=xl_col(j)
            ws.write_formula(debt_map["Beginning Debt"]-1,j,f"={xl_col(j-1)}{debt_map['Ending Debt']}",fmt_formula)
            ws.write_formula(debt_map["Scheduled Repayment"]-1,j,f"=MIN({c}{debt_map['Beginning Debt']},{c}{debt_map['Beginning Debt']}*{A['debt_repayment_pct']})",fmt_formula)
            ws.write_number(debt_map["Debt Draw"]-1,j,0.0,fmt_input_money)
            ws.write_comment(debt_map["Debt Draw"]-1,j,"Editable debt draw assumption. Keep at zero unless financing is required.")
            ws.write_formula(debt_map["Ending Debt"]-1,j,f"=MAX(0,{c}{debt_map['Beginning Debt']}-{c}{debt_map['Scheduled Repayment']}+{c}{debt_map['Debt Draw']})",fmt_formula)
            ws.write_formula(debt_map["Average Debt"]-1,j,f"=AVERAGE({c}{debt_map['Beginning Debt']},{c}{debt_map['Ending Debt']})",fmt_formula)
            ws.write_formula(debt_map["Interest Rate"]-1,j,f"={A['interest_rate']}",fmt_percent_link)
            ws.write_formula(debt_map["Interest Expense"]-1,j,f"={c}{debt_map['Average Debt']}*{c}{debt_map['Interest Rate']}",fmt_formula)

        # ---------------- Forecast IS ----------------
        ws = wb.add_worksheet("Forecast IS")
        setup(ws)
        title(ws, f"Formula-linked income statement forecast. Units: {unit_label}.")
        ws.write(3,0,"Forecast Income Statement",fmt_header_left)
        for j,p in enumerate(forecast_cols,start=1): ws.write(3,j,p,fmt_header_forecast)
        fis_rows=["Revenue","% Growth","COGS","Gross Profit","Gross Margin","EBITDA","EBITDA Margin","D&A","EBIT","Interest Expense","Pretax Income","Tax","Tax Rate","Net Income"]
        fis_map={name:5+i for i,name in enumerate(fis_rows)}
        for i,name in enumerate(fis_rows,start=4): ws.write(i,0,name,fmt_sub_label if ("%" in name or "Margin" in name or name=="Tax Rate") else fmt_label)
        for k,p in enumerate(forecast_cols,start=1):
            c=xl_col(k); source_c=xl_col(n_hist+k)
            ws.write_formula(fis_map["Revenue"]-1,k,f"={quote_sheet('Revenue Build')}!{source_c}5",fmt_link)
            ws.write_formula(fis_map["% Growth"]-1,k,f"={A['revenue_growth']}",fmt_percent_link)
            ws.write_formula(fis_map["COGS"]-1,k,f"={c}{fis_map['Revenue']}*(1-{A['gross_margin']})",fmt_formula)
            ws.write_formula(fis_map["Gross Profit"]-1,k,f"={c}{fis_map['Revenue']}-{c}{fis_map['COGS']}",fmt_formula)
            ws.write_formula(fis_map["Gross Margin"]-1,k,f"=IFERROR({c}{fis_map['Gross Profit']}/{c}{fis_map['Revenue']},0)",fmt_percent)
            ws.write_formula(fis_map["EBITDA"]-1,k,f"={c}{fis_map['Revenue']}*{A['ebitda_margin']}",fmt_formula)
            ws.write_formula(fis_map["EBITDA Margin"]-1,k,f"=IFERROR({c}{fis_map['EBITDA']}/{c}{fis_map['Revenue']},0)",fmt_percent)
            ws.write_formula(fis_map["D&A"]-1,k,f"={quote_sheet('Capex & D&A')}!{source_c}{cap_map['D&A']}",fmt_link)
            ws.write_formula(fis_map["EBIT"]-1,k,f"={c}{fis_map['EBITDA']}-{c}{fis_map['D&A']}",fmt_formula)
            ws.write_formula(fis_map["Interest Expense"]-1,k,f"={quote_sheet('Debt Schedule')}!{source_c}{debt_map['Interest Expense']}",fmt_link)
            ws.write_formula(fis_map["Pretax Income"]-1,k,f"={c}{fis_map['EBIT']}-{c}{fis_map['Interest Expense']}",fmt_formula)
            ws.write_formula(fis_map["Tax"]-1,k,f"=MAX(0,{c}{fis_map['Pretax Income']}*{A['tax_rate']})",fmt_formula)
            ws.write_formula(fis_map["Tax Rate"]-1,k,f"=IFERROR({c}{fis_map['Tax']}/{c}{fis_map['Pretax Income']},0)",fmt_percent)
            ws.write_formula(fis_map["Net Income"]-1,k,f"={c}{fis_map['Pretax Income']}-{c}{fis_map['Tax']}",fmt_total)

        # ---------------- Forecast CF ----------------
        ws = wb.add_worksheet("Forecast CF")
        setup(ws)
        title(ws, f"Formula-linked cash flow forecast. Units: {unit_label}.")
        ws.write(3,0,"Forecast Cash Flow Statement",fmt_header_left)
        for j,p in enumerate(forecast_cols,start=1): ws.write(3,j,p,fmt_header_forecast)
        fcf_rows=["Net Income","D&A","Change in NWC","CFO","Capex","Debt Issuance/(Repayment)","Dividends","Net Change in Cash","Beginning Cash","Ending Cash","FCF"]
        fcf_map={name:5+i for i,name in enumerate(fcf_rows)}
        for i,name in enumerate(fcf_rows,start=4): ws.write(i,0,name,fmt_label)
        for k,p in enumerate(forecast_cols,start=1):
            c=xl_col(k); source_c=xl_col(n_hist+k)
            ws.write_formula(fcf_map["Net Income"]-1,k,f"={quote_sheet('Forecast IS')}!{c}{fis_map['Net Income']}",fmt_link)
            ws.write_formula(fcf_map["D&A"]-1,k,f"={quote_sheet('Forecast IS')}!{c}{fis_map['D&A']}",fmt_link)
            ws.write_formula(fcf_map["Change in NWC"]-1,k,f"={quote_sheet('Working Capital')}!{source_c}{wc_map['Change in NWC']}",fmt_link)
            ws.write_formula(fcf_map["CFO"]-1,k,f"={c}{fcf_map['Net Income']}+{c}{fcf_map['D&A']}-{c}{fcf_map['Change in NWC']}",fmt_formula)
            ws.write_formula(fcf_map["Capex"]-1,k,f"=-{quote_sheet('Capex & D&A')}!{source_c}{cap_map['Capex']}",fmt_link)
            ws.write_formula(fcf_map["Debt Issuance/(Repayment)"]-1,k,f"={quote_sheet('Debt Schedule')}!{source_c}{debt_map['Debt Draw']}-{quote_sheet('Debt Schedule')}!{source_c}{debt_map['Scheduled Repayment']}",fmt_link)
            ws.write_formula(fcf_map["Dividends"]-1,k,f"=-MAX(0,{c}{fcf_map['Net Income']}*{A['dividend_payout']})",fmt_formula)
            ws.write_formula(fcf_map["Net Change in Cash"]-1,k,f"=SUM({c}{fcf_map['CFO']}:{c}{fcf_map['Dividends']})",fmt_total)
            if k==1:
                ws.write_formula(fcf_map["Beginning Cash"]-1,k,f"={href('Historical BS','Cash')}",fmt_link)
            else:
                ws.write_formula(fcf_map["Beginning Cash"]-1,k,f"={xl_col(k-1)}{fcf_map['Ending Cash']}",fmt_formula)
            ws.write_formula(fcf_map["Ending Cash"]-1,k,f"={c}{fcf_map['Beginning Cash']}+{c}{fcf_map['Net Change in Cash']}",fmt_formula)
            ws.write_formula(fcf_map["FCF"]-1,k,f"={c}{fcf_map['CFO']}+{c}{fcf_map['Capex']}",fmt_total)

        # ---------------- Forecast BS ----------------
        ws = wb.add_worksheet("Forecast BS")
        setup(ws)
        title(ws, f"Formula-linked balance sheet forecast. Units: {unit_label}.")
        ws.write(3,0,"Forecast Balance Sheet",fmt_header_left)
        for j,p in enumerate(forecast_cols,start=1): ws.write(3,j,p,fmt_header_forecast)
        fbs_rows=["Cash","Accounts Receivable","Inventory","Net PPE","Other Assets","Total Assets","Accounts Payable","Total Debt","Other Liabilities (Plug)","Equity","Total Liabilities & Equity","Balance Check"]
        fbs_map={name:5+i for i,name in enumerate(fbs_rows)}
        for i,name in enumerate(fbs_rows,start=4): ws.write(i,0,name,fmt_label)
        # Historical residuals in mm
        last = hist_cols[-1]
        last_cash=float(hist_mm.loc["Cash",last]); last_ar=float(hist_mm.loc["Accounts Receivable",last]); last_inv=float(hist_mm.loc["Inventory",last]); last_ppe=float(hist_mm.loc["Net PPE",last])
        last_assets=float(hist_mm.loc["Total Assets",last]); last_debt=float(hist_mm.loc["Total Debt",last]); last_ap=float(hist_mm.loc["Accounts Payable",last]); last_equity=float(hist_mm.loc["Equity",last])
        other_assets=max(0.0,last_assets-last_cash-last_ar-last_inv-last_ppe)
        for k,p in enumerate(forecast_cols,start=1):
            c=xl_col(k); source_c=xl_col(n_hist+k)
            ws.write_formula(fbs_map["Cash"]-1,k,f"={quote_sheet('Forecast CF')}!{c}{fcf_map['Ending Cash']}",fmt_link)
            ws.write_formula(fbs_map["Accounts Receivable"]-1,k,f"={quote_sheet('Working Capital')}!{source_c}{wc_map['Accounts Receivable']}",fmt_link)
            ws.write_formula(fbs_map["Inventory"]-1,k,f"={quote_sheet('Working Capital')}!{source_c}{wc_map['Inventory']}",fmt_link)
            ws.write_formula(fbs_map["Net PPE"]-1,k,f"={quote_sheet('Capex & D&A')}!{source_c}{cap_map['Ending Net PPE']}",fmt_link)
            if k==1:
                ws.write_number(fbs_map["Other Assets"]-1,k,other_assets,fmt_hardcode)
                ws.write_comment(fbs_map["Other Assets"]-1,k,"Historical residual (Total Assets less Cash, AR, Inventory and Net PPE). Held flat in generic corporate forecast.")
            else:
                ws.write_formula(fbs_map["Other Assets"]-1,k,f"={xl_col(k-1)}{fbs_map['Other Assets']}",fmt_formula)
            ws.write_formula(fbs_map["Total Assets"]-1,k,f"=SUM({c}{fbs_map['Cash']}:{c}{fbs_map['Other Assets']})",fmt_total)
            ws.write_formula(fbs_map["Accounts Payable"]-1,k,f"={quote_sheet('Working Capital')}!{source_c}{wc_map['Accounts Payable']}",fmt_link)
            ws.write_formula(fbs_map["Total Debt"]-1,k,f"={quote_sheet('Debt Schedule')}!{source_c}{debt_map['Ending Debt']}",fmt_link)
            if k==1:
                prev_eq=href('Historical BS','Equity')
            else:
                prev_eq=f"{xl_col(k-1)}{fbs_map['Equity']}"
            ws.write_formula(fbs_map["Equity"]-1,k,f"={prev_eq}+{quote_sheet('Forecast IS')}!{c}{fis_map['Net Income']}+{quote_sheet('Forecast CF')}!{c}{fcf_map['Dividends']}",fmt_formula)
            # Generic balancing residual - transparent plug.
            ws.write_formula(fbs_map["Other Liabilities (Plug)"]-1,k,f"={c}{fbs_map['Total Assets']}-{c}{fbs_map['Accounts Payable']}-{c}{fbs_map['Total Debt']}-{c}{fbs_map['Equity']}",fmt_formula)
            ws.write_formula(fbs_map["Total Liabilities & Equity"]-1,k,f"=SUM({c}{fbs_map['Accounts Payable']}:{c}{fbs_map['Equity']})",fmt_total)
            ws.write_formula(fbs_map["Balance Check"]-1,k,f"={c}{fbs_map['Total Assets']}-{c}{fbs_map['Total Liabilities & Equity']}",fmt_formula)
        ws.write_comment(fbs_map["Other Liabilities (Plug)"]-1,1,"Generic corporate model balancing residual. Banks, insurers, NBFCs and REITs require sector-specific models.")

        # ---------------- DCF ----------------
        ws = wb.add_worksheet("DCF")
        setup(ws)
        title(ws, f"Discounted cash flow valuation. Units: {unit_label} except per-share data.")
        ws.write(3,0,"DCF Valuation",fmt_header_left)
        for j,p in enumerate(forecast_cols,start=1): ws.write(3,j,p,fmt_header_forecast)
        dcf_rows=["EBIT","Tax Rate","NOPAT","D&A","Capex","Change in NWC","UFCF","Discount Period","Discount Factor","PV of UFCF"]
        dcf_map={name:5+i for i,name in enumerate(dcf_rows)}
        for i,name in enumerate(dcf_rows,start=4): ws.write(i,0,name,fmt_sub_label if name in ["Tax Rate","Discount Period","Discount Factor"] else fmt_label)
        for k,p in enumerate(forecast_cols,start=1):
            c=xl_col(k); source_c=xl_col(n_hist+k)
            ws.write_formula(dcf_map["EBIT"]-1,k,f"={quote_sheet('Forecast IS')}!{c}{fis_map['EBIT']}",fmt_link)
            ws.write_formula(dcf_map["Tax Rate"]-1,k,f"={A['tax_rate']}",fmt_percent_link)
            ws.write_formula(dcf_map["NOPAT"]-1,k,f"={c}{dcf_map['EBIT']}*(1-{c}{dcf_map['Tax Rate']})",fmt_formula)
            ws.write_formula(dcf_map["D&A"]-1,k,f"={quote_sheet('Forecast IS')}!{c}{fis_map['D&A']}",fmt_link)
            ws.write_formula(dcf_map["Capex"]-1,k,f"={quote_sheet('Forecast CF')}!{c}{fcf_map['Capex']}",fmt_link)
            ws.write_formula(dcf_map["Change in NWC"]-1,k,f"={quote_sheet('Forecast CF')}!{c}{fcf_map['Change in NWC']}",fmt_link)
            ws.write_formula(dcf_map["UFCF"]-1,k,f"={c}{dcf_map['NOPAT']}+{c}{dcf_map['D&A']}+{c}{dcf_map['Capex']}-{c}{dcf_map['Change in NWC']}",fmt_formula)
            ws.write_number(dcf_map["Discount Period"]-1,k,k,fmt_formula)
            wacc_ref=M["WACC Override"]
            ws.write_formula(dcf_map["Discount Factor"]-1,k,f"=1/(1+{wacc_ref})^{c}{dcf_map['Discount Period']}",fmt_formula)
            ws.write_formula(dcf_map["PV of UFCF"]-1,k,f"={c}{dcf_map['UFCF']}*{c}{dcf_map['Discount Factor']}",fmt_formula)
        vr=17
        ws.write(vr,0,"Valuation Bridge",fmt_section); vr+=1
        bridge = [
            ("WACC", f"={M['WACC Override']}", "pct"),
            ("Terminal Growth", f"={A['terminal_growth']}", "pct"),
            ("PV Forecast UFCF", f"=SUM(B{dcf_map['PV of UFCF']}:{xl_col(n_fc)}{dcf_map['PV of UFCF']})", "money"),
            ("Terminal Value", f"={xl_col(n_fc)}{dcf_map['UFCF']}*(1+B{vr+2})/(B{vr+1}-B{vr+2})", "money"),
            ("PV Terminal Value", f"=B{vr+4}/(1+B{vr+1})^{n_fc}", "money"),
            ("Enterprise Value", f"=B{vr+3}+B{vr+5}", "money"),
            ("Less: Debt", f"=-{href('Historical BS','Total Debt')}", "money"),
            ("Add: Cash", f"={href('Historical BS','Cash')}", "money"),
            ("Equity Value", f"=SUM(B{vr+6}:B{vr+8})", "money"),
            ("Shares Outstanding (Cr)", f"={M['Shares Outstanding (Cr)']}", "money"),
            ("Implied Price", f"=IFERROR(B{vr+9}/B{vr+10},0)", "price"),
            ("Current Price", f"={M['Current Share Price']}", "price"),
            ("Upside / (Downside)", f"=IFERROR(B{vr+11}/B{vr+12}-1,0)", "pct"),
        ]
        dcf_bridge_rows={}
        for idx,(label,formula,kind) in enumerate(bridge):
            rr=vr+idx+1; dcf_bridge_rows[label]=rr+1
            ws.write(rr,0,label,fmt_total_label if label in ["Enterprise Value","Equity Value","Implied Price"] else fmt_label)
            fm = fmt_percent if kind=="pct" else (fmt_price if kind=="price" else fmt_formula)
            if label in ["Enterprise Value","Equity Value","Implied Price"]:
                fm = fmt_total if kind=="money" else fmt_price
            ws.write_formula(rr,1,formula,fm)

        # ---------------- Comps ----------------
        ws = wb.add_worksheet("Comps")
        setup(ws)
        title(ws, "Trading comparable companies. Hardcoded market data from the model run.")
        if comps is None or comps.empty:
            ws.write(4,0,"No peer tickers were supplied. Rerun the app with peers to populate this sheet.",fmt_note)
        else:
            comp_cols=list(comps.columns)
            for j,cname in enumerate(comp_cols): ws.write(3,j,cname,fmt_header_left if j<2 else fmt_header)
            for i,(_,row) in enumerate(comps.iterrows(),start=4):
                for j,cname in enumerate(comp_cols):
                    val=row[cname]
                    if pd.isna(val): ws.write_blank(i,j,None,fmt_hardcode)
                    elif isinstance(val,(int,float,np.number)):
                        f=fmt_multiple if cname in ["Trailing P/E","Forward P/E","EV/Revenue","EV/EBITDA","Price/Book"] else fmt_hardcode
                        if cname in ["Market Cap","Enterprise Value"]:
                            ws.write_number(i,j,float(val)/scale,fmt_hardcode)
                        else:
                            ws.write_number(i,j,float(val),f)
                    else: ws.write(i,j,str(val),fmt_text)
                    ws.write_comment(i,j,source_comment)
            ws.autofilter(3,0,3+len(comps),len(comp_cols)-1)

        # ---------------- Sensitivity ----------------
        ws = wb.add_worksheet("Sensitivity")
        setup(ws)
        title(ws, "DCF implied price sensitivity to WACC and terminal growth.")
        ws.write(3,0,"Implied Price Sensitivity",fmt_section)
        waccs=[0.07,0.08,0.09,0.10,0.11,0.12,0.13]
        tgs=[0.01,0.015,0.02,0.025,0.03,0.035,0.04]
        ws.write(4,0,"WACC / Terminal Growth",fmt_header_left)
        for j,g in enumerate(tgs,start=1): ws.write_number(4,j,g,fmt_percent_input)
        # DCF refs
        ufcf_row=dcf_map["UFCF"]
        debt_ref=href('Historical BS','Total Debt'); cash_ref=href('Historical BS','Cash'); shares_ref=M['Shares Outstanding (Cr)']
        for i,wacc in enumerate(waccs,start=5):
            ws.write_number(i,0,wacc,fmt_percent_input)
            for j,g in enumerate(tgs,start=1):
                # Sum PV forecast explicitly + terminal value formula using row/column sensitivity inputs.
                pv_terms=[]
                for k in range(1,n_fc+1):
                    c=xl_col(k)
                    pv_terms.append(f"{quote_sheet('DCF')}!{c}{ufcf_row}/(1+$A{i+1})^{k}")
                last_c=xl_col(n_fc)
                terminal=f"({quote_sheet('DCF')}!{last_c}{ufcf_row}*(1+{xl_col(j)}$5)/($A{i+1}-{xl_col(j)}$5))/(1+$A{i+1})^{n_fc}"
                formula=f"=IFERROR((({'+'.join(pv_terms)})+{terminal}-{debt_ref}+{cash_ref})/{shares_ref},0)"
                ws.write_formula(i,j,formula,fmt_price)
        ws.conditional_format(5,1,5+len(waccs)-1,1+len(tgs)-1,{"type":"3_color_scale","min_color":"#F8696B","mid_color":"#FFEB84","max_color":"#63BE7B"})

        # ---------------- Scenario Analysis ----------------
        ws = wb.add_worksheet("Scenario Analysis")
        setup(ws)
        title(ws, "Bear / Base / Bull output comparison from the modelling engine.")
        ws.write_row(3,0,["Metric","Bear","Base","Bull"],fmt_header_left)
        metric_list=["Revenue","EBITDA","Net Income","FCF","Cash","Total Debt"]
        last_fc=forecast_cols[-1]
        for i,metric in enumerate(metric_list,start=4):
            ws.write(i,0,f"{last_fc} {metric}",fmt_label)
            for j,sc in enumerate(["Bear","Base","Bull"],start=1):
                val=float(forecasts[sc].loc[metric,last_fc])/scale if metric in forecasts[sc].index else 0.0
                ws.write_number(i,j,val,fmt_hardcode)
                ws.write_comment(i,j,"Scenario output generated by the modelling engine using scenario-specific assumptions.")
        # engine DCF / MC context
        i=4+len(metric_list)+1
        ws.write(i,0,"Model DCF Implied Price (Base)",fmt_label); ws.write_number(i,2,float(result['valuation'].get('Implied Price') or 0),fmt_hardcode)
        ws.write(i+1,0,"Monte Carlo P10",fmt_label); ws.write_number(i+1,2,float(result['monte_carlo'].get('p10') or 0),fmt_hardcode)
        ws.write(i+2,0,"Monte Carlo Median",fmt_label); ws.write_number(i+2,2,float(result['monte_carlo'].get('p50') or 0),fmt_hardcode)
        ws.write(i+3,0,"Monte Carlo P90",fmt_label); ws.write_number(i+3,2,float(result['monte_carlo'].get('p90') or 0),fmt_hardcode)

        # ---------------- KPIs ----------------
        ws = wb.add_worksheet("KPIs")
        setup(ws)
        title(ws, "Historical and model KPI summary.")
        kpis=result['kpis'].copy()
        ws.write(3,0,"KPI",fmt_header_left)
        for j,p in enumerate(kpis.index,start=1): ws.write(3,j,str(p),fmt_header)
        for i,cname in enumerate(kpis.columns,start=4):
            ws.write(i,0,cname,fmt_label)
            is_pct=any(x in cname for x in ["Margin","Growth","ROE","ROA"])
            for j,p in enumerate(kpis.index,start=1):
                v=kpis.loc[p,cname]
                if pd.isna(v): ws.write_blank(i,j,None,fmt_formula)
                else: ws.write_number(i,j,float(v),fmt_percent if is_pct else fmt_formula)

        # ---------------- Model Checks ----------------
        ws = wb.add_worksheet("Model Checks")
        setup(ws)
        title(ws, "Audit checks. Green = pass; red = fail / investigate.")
        ws.write_row(3,0,["Check","Scenario","Period","Value","Status"],fmt_header_left)
        row=4
        if audit:
            for item in audit:
                ws.write(row,0,str(item.get("Check","")),fmt_label)
                ws.write(row,1,str(item.get("Scenario","")),fmt_text)
                ws.write(row,2,str(item.get("Period","")),fmt_text)
                val=item.get("Value")
                if isinstance(val,(int,float,np.number)) and not pd.isna(val): ws.write_number(row,3,float(val)/scale if abs(float(val))>100000 else float(val),fmt_formula)
                else: ws.write(row,3,"" if val is None else str(val),fmt_text)
                status=str(item.get("Status",""))
                ws.write(row,4,status,fmt_check_ok if status=="PASS" else fmt_check_bad)
                row+=1
        # linked live checks from workbook
        row+=1
        ws.write(row,0,"Live Workbook Checks",fmt_section); row+=1
        for k,p in enumerate(forecast_cols,start=1):
            c=xl_col(k)
            ws.write(row,0,"Balance Sheet Check",fmt_label); ws.write(row,1,"Selected",fmt_text); ws.write(row,2,p,fmt_text)
            ws.write_formula(row,3,f"={quote_sheet('Forecast BS')}!{c}{fbs_map['Balance Check']}",fmt_formula)
            ws.write_formula(row,4,f'=IF(ABS(D{row+1})<0.1,"PASS","FAIL")',fmt_check_ok)
            row+=1
            ws.write(row,0,"Cash Roll-forward Check",fmt_label); ws.write(row,1,"Selected",fmt_text); ws.write(row,2,p,fmt_text)
            if k==1:
                beginning=href('Historical BS','Cash')
            else:
                beginning=f"{quote_sheet('Forecast CF')}!{xl_col(k-1)}{fcf_map['Ending Cash']}"
            ws.write_formula(row,3,f"={quote_sheet('Forecast CF')}!{c}{fcf_map['Ending Cash']}-{beginning}-{quote_sheet('Forecast CF')}!{c}{fcf_map['Net Change in Cash']}",fmt_formula)
            ws.write_formula(row,4,f'=IF(ABS(D{row+1})<0.1,"PASS","FAIL")',fmt_check_ok)
            row+=1
        ws.conditional_format(4,4,row,4,{"type":"text","criteria":"containing","value":"FAIL","format":fmt_check_bad})

        # ---------------- Dashboard ----------------
        ws = wb.add_worksheet("Dashboard")
        setup(ws, None)
        ws.set_zoom(85)
        ws.set_column(0, 0, 2)
        ws.set_column(1, 16, 12)
        ws.set_row(0, 8)
        ws.merge_range("B2:Q3", f"{company} ({ticker}) — Executive Financial Dashboard", fmt_title)
        ws.merge_range("B4:Q4", f"Formula-linked dashboard | Selected scenario: Assumptions!B4 | Units: {unit_label}", fmt_subtitle)

        # Six presentation-ready KPI cards.
        card_specs = [
            ("Current Price", M['Current Share Price'], "num"),
            ("DCF Implied Price", f"DCF!$B${dcf_bridge_rows['Implied Price']}", "num"),
            ("Upside / (Downside)", f"DCF!$B${dcf_bridge_rows['Upside / (Downside)']}", "pct"),
            ("WACC", M['WACC Override'], "pct"),
            ("Terminal Growth", A['terminal_growth'], "pct"),
            ("MC Median Price", None, "num"),
        ]
        starts = [1, 4, 7, 10, 13, 16]
        for idx, (lab, ref, col) in enumerate(zip([x[0] for x in card_specs], [x[1] for x in card_specs], starts)):
            ws.merge_range(6, col, 6, col + 1, lab, fmt_dash_labels[idx])
            if lab == "MC Median Price":
                val = float(result.get("monte_carlo", {}).get("p50") or 0)
                ws.merge_range(7, col, 8, col + 1, val, fmt_dash_values[idx])
            else:
                kind = card_specs[idx][2]
                fmtv = fmt_dash_values_pct[idx] if kind == "pct" else fmt_dash_values[idx]
                ws.merge_range(7, col, 8, col + 1, f"={ref}", fmtv)
        ws.set_row(6, 22); ws.set_row(7, 26); ws.set_row(8, 26)

        # Section headings give the dashboard a clean presentation hierarchy.
        ws.merge_range("B10:I10", "Financial Outlook", fmt_dash_section)
        ws.merge_range("J10:Q10", "Valuation & Scenarios", fmt_dash_section)

        # Chart data block (kept below presentation area).
        data_start = 39
        ws.write(data_start, 1, "Period", fmt_header_left)
        for cidx, h in enumerate(["Revenue", "EBITDA", "Net Income", "FCF", "EBITDA Margin", "FCF Margin"], start=2):
            ws.write(data_start, cidx, h, fmt_header_forecast)
        for k, p in enumerate(forecast_cols, start=1):
            rr = data_start + k
            c = xl_col(k)
            ws.write(rr, 1, p, fmt_text)
            ws.write_formula(rr, 2, f"={quote_sheet('Forecast IS')}!{c}{fis_map['Revenue']}", fmt_link)
            ws.write_formula(rr, 3, f"={quote_sheet('Forecast IS')}!{c}{fis_map['EBITDA']}", fmt_link)
            ws.write_formula(rr, 4, f"={quote_sheet('Forecast IS')}!{c}{fis_map['Net Income']}", fmt_link)
            ws.write_formula(rr, 5, f"={quote_sheet('Forecast CF')}!{c}{fcf_map['FCF']}", fmt_link)
            ws.write_formula(rr, 6, f"=IFERROR(D{rr+1}/C{rr+1},0)", fmt_percent)
            ws.write_formula(rr, 7, f"=IFERROR(F{rr+1}/C{rr+1},0)", fmt_percent)

        # Chart 1: revenue bars + profitability/cash lines.
        rev_chart = wb.add_chart({"type": "column"})
        rev_chart.add_series({
            "name": "Revenue",
            "categories": ["Dashboard", data_start + 1, 1, data_start + n_fc, 1],
            "values": ["Dashboard", data_start + 1, 2, data_start + n_fc, 2],
            "fill": {"color": "#4472C4"}, "border": {"none": True},
        })
        line_chart = wb.add_chart({"type": "line"})
        for col, name, color in [(3, "EBITDA", "#70AD47"), (4, "Net Income", "#7030A0"), (5, "FCF", "#ED7D31")]:
            line_chart.add_series({
                "name": name,
                "categories": ["Dashboard", data_start + 1, 1, data_start + n_fc, 1],
                "values": ["Dashboard", data_start + 1, col, data_start + n_fc, col],
                "line": {"color": color, "width": 2.25},
                "marker": {"type": "circle", "size": 5, "border": {"color": color}, "fill": {"color": "#FFFFFF"}},
            })
        rev_chart.combine(line_chart)
        rev_chart.set_title({"name": "Forecast Revenue, Earnings & Free Cash Flow"})
        rev_chart.set_legend({"position": "bottom"})
        rev_chart.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})
        rev_chart.set_chartarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        rev_chart.set_plotarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        rev_chart.set_style(10)
        ws.insert_chart("B11", rev_chart, {"x_scale": 1.25, "y_scale": 1.12})

        # Chart 2: margin trend.
        margin_chart = wb.add_chart({"type": "line"})
        for col, name, color in [(6, "EBITDA Margin", "#70AD47"), (7, "FCF Margin", "#ED7D31")]:
            margin_chart.add_series({
                "name": name,
                "categories": ["Dashboard", data_start + 1, 1, data_start + n_fc, 1],
                "values": ["Dashboard", data_start + 1, col, data_start + n_fc, col],
                "line": {"color": color, "width": 2.5},
                "marker": {"type": "diamond", "size": 5},
            })
        margin_chart.set_title({"name": "Margin Outlook"})
        margin_chart.set_legend({"position": "bottom"})
        margin_chart.set_y_axis({"num_format": "0.0%", "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})
        margin_chart.set_chartarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        margin_chart.set_plotarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        ws.insert_chart("B25", margin_chart, {"x_scale": 1.25, "y_scale": 0.9})

        # Valuation comparison block and chart.
        val_row = data_start
        ws.write(val_row, 10, "Valuation Method", fmt_header_left)
        ws.write(val_row, 11, "Price", fmt_header_forecast)
        valuation_rows = [
            ("Current Price", f"={M['Current Share Price']}", None),
            ("DCF Implied Price", f"=DCF!$B${dcf_bridge_rows['Implied Price']}", None),
            ("Monte Carlo Median", None, float(result.get("monte_carlo", {}).get("p50") or 0)),
        ]
        for i, (label, formula, value) in enumerate(valuation_rows, start=1):
            ws.write(val_row + i, 10, label, fmt_label)
            if formula:
                ws.write_formula(val_row + i, 11, formula, fmt_price)
            else:
                ws.write_number(val_row + i, 11, value, fmt_price)
        val_chart = wb.add_chart({"type": "column"})
        val_chart.add_series({
            "name": "Per Share Value",
            "categories": ["Dashboard", val_row + 1, 10, val_row + 3, 10],
            "values": ["Dashboard", val_row + 1, 11, val_row + 3, 11],
            "points": [
                {"fill": {"color": "#A5A5A5"}},
                {"fill": {"color": "#4472C4"}},
                {"fill": {"color": "#70AD47"}},
            ],
            "border": {"none": True},
            "data_labels": {"value": True, "num_format": "0.00"},
        })
        val_chart.set_title({"name": "Valuation Comparison"})
        val_chart.set_legend({"none": True})
        val_chart.set_y_axis({"num_format": "0.00", "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})
        val_chart.set_chartarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        val_chart.set_plotarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        ws.insert_chart("J11", val_chart, {"x_scale": 1.05, "y_scale": 1.12})

        # Scenario chart uses final-year EBITDA for Bear / Base / Bull.
        scen_row = data_start + 6
        ws.write(scen_row, 10, "Scenario", fmt_header_left)
        ws.write(scen_row, 11, f"{forecast_cols[-1]} EBITDA", fmt_header_forecast)
        for idx, scen in enumerate(["Bear", "Base", "Bull"], start=1):
            ws.write(scen_row + idx, 10, scen, fmt_text)
            val = float(forecasts[scen].loc["EBITDA", forecast_cols[-1]]) / scale if "EBITDA" in forecasts[scen].index else 0.0
            ws.write_number(scen_row + idx, 11, val, fmt_hardcode)
        scen_chart = wb.add_chart({"type": "column"})
        scen_chart.add_series({
            "name": "EBITDA",
            "categories": ["Dashboard", scen_row + 1, 10, scen_row + 3, 10],
            "values": ["Dashboard", scen_row + 1, 11, scen_row + 3, 11],
            "points": [
                {"fill": {"color": "#C00000"}},
                {"fill": {"color": "#4472C4"}},
                {"fill": {"color": "#70AD47"}},
            ],
            "border": {"none": True},
            "data_labels": {"value": True, "num_format": "#,##0.0"},
        })
        scen_chart.set_title({"name": "Scenario EBITDA"})
        scen_chart.set_legend({"none": True})
        scen_chart.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E7E6E6"}}})
        scen_chart.set_chartarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        scen_chart.set_plotarea({"border": {"none": True}, "fill": {"color": "#FFFFFF"}})
        ws.insert_chart("J25", scen_chart, {"x_scale": 1.05, "y_scale": 0.9})

        # Dashboard footer / legend.
        ws.merge_range("B37:Q37", "Model convention: Blue = inputs / forecast headers | Green = same-workbook links | Black = formulas | Yellow = editable assumptions | Red parentheses = negatives", fmt_note)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)
        ws.set_margins(0.25, 0.25, 0.4, 0.4)

        # ---------------- Sources ----------------
        ws = wb.add_worksheet("Sources")
        setup(ws,None)
        title(ws,"Data provenance and model methodology.")
        sources=[
            ("Actual financial statements",source,meta.get("Data Timestamp UTC"),"Historical IS / BS / CF"),
            ("Market data",source,meta.get("Data Timestamp UTC"),"Assumptions / Comps"),
            ("Model forecasts","FinModel AI deterministic driver model","Generated at runtime","Revenue Build / schedules / Forecast statements"),
            ("Valuation","Formula-linked DCF using selected assumptions","Generated at runtime","DCF / Sensitivity"),
        ]
        ws.write_row(3,0,["Data / Method","Source","Timestamp","Used In"],fmt_header_left)
        for i,rowv in enumerate(sources,start=4):
            for j,v in enumerate(rowv): ws.write(i,j,"" if v is None else str(v),fmt_text)
        ws.set_column(0,0,28);ws.set_column(1,1,45);ws.set_column(2,3,28)
        ws.merge_range(10,0,13,5,
                       "Important: the workbook separates source actuals from model assumptions and formulas. Verify material figures against audited filings and primary company disclosures. Generic corporate balance-sheet forecasting uses Other Liabilities as a transparent balancing residual; sector-specific financial institutions require dedicated models.",
                       fmt_note)

        # Ensure Cover opens first / Dashboard immediately after.
        wb.get_worksheet_by_name("Cover").activate()
        wb.close()
        return str(outpath)

    def power_bi_tables(self, result):
        ticker = result["meta"]["Ticker"]
        hist = result["historical"]
        forecasts = result["forecasts"]
        kpis = result["kpis"]

        actual = hist.T.reset_index(names="Period").melt(id_vars="Period", var_name="Metric", value_name="Value")
        actual["Company"] = ticker
        actual["DataType"] = "Actual"

        fs = []
        for scen, df in forecasts.items():
            x = df.T.reset_index(names="Period").melt(id_vars="Period", var_name="Metric", value_name="Value")
            x["Company"] = ticker
            x["Scenario"] = scen
            x["DataType"] = "Model Forecast"
            fs.append(x)
        forecast_long = pd.concat(fs, ignore_index=True)

        kpi_long = kpis.reset_index(names="Period").melt(id_vars="Period", var_name="KPI", value_name="Value")
        kpi_long["Company"] = ticker

        valuation = pd.DataFrame([self._serializable_valuation(result["valuation"])])
        valuation["Company"] = ticker
        assumptions = pd.DataFrame([result["assumptions"]])
        assumptions["Company"] = ticker
        company = pd.DataFrame([result["meta"]])
        audit = pd.DataFrame(result["audit"])
        if not audit.empty:
            audit["Company"] = ticker

        periods = sorted(set(actual["Period"].astype(str)).union(set(forecast_long["Period"].astype(str))))
        period_dim = pd.DataFrame({"Period": periods})
        period_dim["Year"] = pd.to_numeric(period_dim["Period"].str.extract(r"(\d{4})")[0], errors="coerce")
        period_dim["Type"] = period_dim["Period"].str[-1].map({"A": "Actual", "E": "Forecast"}).fillna("Other")

        tables = {
            "Company": company,
            "Period": period_dim,
            "FinancialActuals": actual,
            "Forecasts": forecast_long,
            "KPIs": kpi_long,
            "Valuation": valuation,
            "Assumptions": assumptions,
            "ModelChecks": audit,
            "MonteCarlo": pd.DataFrame([result["monte_carlo"]]).assign(Company=ticker),
            "ReverseDCF": pd.DataFrame([result["reverse_dcf"]]).assign(Company=ticker),
        }
        if result["comps"] is not None and not result["comps"].empty:
            tables["TradingComps"] = result["comps"]
        return tables
