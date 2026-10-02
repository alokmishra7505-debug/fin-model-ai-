"""Portable Python exports. Amounts are scaled once; prices and shares are not."""
from dataclasses import asdict
from io import BytesIO
import numpy as np
import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
from .forecasting import LABELS
from .utils import finite, as_float
from .kpis import PERCENT_KPIS, DAY_KPIS

SHEETS = ["Cover", "Assumptions", "Historical IS", "Historical BS", "Historical CF", "Revenue Build",
          "Working Capital", "Capex & Depreciation", "Debt Schedule", "Forecast IS", "Forecast BS", "Forecast CF",
          "DCF", "Comps", "Sensitivity", "Scenario Analysis", "KPIs", "Model Checks", "Dashboard", "Sources"]


def excel_number(value, scale=1):
    """Convert before scaling; missing/non-finite results stay unavailable, never zero."""
    if not finite(value):
        return "N/A"
    result = float(value) / scale
    return result if finite(result) else "N/A"


def write_numeric(ws, row, col, value, cell_format=None, scale=1):
    return ws.write(row, col, excel_number(value, scale), cell_format)


def write_cached_formula(ws, row, col, expression, cell_format, value):
    # Formula caches must also exclude NaN/Infinity: Excel XML cannot store them.
    return ws.write_formula(row, col, expression, cell_format, excel_number(value))


def missing_number_handler(ws, row, col, value, cell_format=None):
    if not finite(value):
        return ws.write_string(row, col, "N/A", cell_format)
    return None  # Let XlsxWriter write an ordinary finite number.


def excel_workbook(bundle, units, comps=None):
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
    wb.set_properties({"title":f"FinModel AI | {bundle.data.name}","author":"FinModel AI"})
    wb.set_calc_mode("auto")
    sheets = {name:wb.add_worksheet(name) for name in SHEETS}
    base_style = {"font_name":"Arial","font_size":10,"valign":"vcenter"}
    title = wb.add_format({**base_style,"font_size":16,"bold":True,"font_color":"#172b4d"})
    header = wb.add_format({**base_style,"bold":True,"bg_color":"#172b4d","font_color":"white","text_wrap":True})
    forecast_header = wb.add_format({**base_style,"bold":True,"bg_color":"#087f8c","font_color":"white","text_wrap":True})
    note = wb.add_format({**base_style,"font_color":"#52647a","text_wrap":True})
    text_fmt = wb.add_format(base_style)
    styles = {}
    formats = {"money": '#,##0.0;[Red](#,##0.0);"-"', "price":'#,##0.00;[Red](#,##0.00);"-"',
               "pct":'0.0%;[Red](0.0%);"-"', "number":'#,##0.0;[Red](#,##0.0);"-"',
               "shares":'#,##0;[Red](#,##0);"-"',"multiple":'0.00"x";[Red](0.00"x");"-"',"check":'0.00;[Red](0.00);0.00'}
    for kind,code in formats.items():
        for role,color in (("input","#0000ff"),("link","#008000"),("formula","#000000"),("edit","#0000ff")):
            styles[kind,role] = wb.add_format({**base_style,"num_format":code,"font_color":color,
                **({"bg_color":"#fff2cc"} if role=="edit" else {}), **({"italic":True} if kind in ("pct","multiple") else {})})
    for name,ws in sheets.items():
        for number_type in (float, np.float64, np.float32):
            ws.add_write_handler(number_type, missing_number_handler)
        ws.hide_gridlines(2)
        ws.freeze_panes(5,1)
        ws.set_column(0,0,38)
        ws.set_column(1,10,21)
        ws.set_default_row(20)
        ws.set_row(1,26)
        ws.set_row(2,42)
        ws.set_row(4,32)
        ws.write(1,0,f"FinModel AI | {name}",title)
        ws.merge_range(2,0,2,7,f"{bundle.data.ticker} · {units.label} except per-share prices, ratios and shares · Base model",note)
        ws.set_tab_color("#087f8c" if name in ("Cover","Dashboard","DCF") else "#71839a")
        ws.set_landscape()
        ws.fit_to_pages(1,0)
        ws.repeat_rows(4)
    maps = {}
    frame_lookup = {}

    def metric_kind(row):
        if row in PERCENT_KPIS or "margin" in row.lower() or row in ("Revenue growth","Tax rate","Interest rate","Discount Factor"):
            return "pct"
        if row in ("EPS","EPS change","Current Price","Implied Price"):
            return "price"
        if row=="Shares":
            return "shares"
        if row.endswith("days"):
            return "number"
        if row in ("Balance Check","Cash Reconciliation"):
            return "check"
        return "money"

    def table(name,frame,forecast=False):
        ws = sheets[name]
        frame_lookup[name] = frame
        maps[name] = {row:idx+5 for idx,row in enumerate(frame.index)}
        ws.write(4,0,"Metric",header)
        for c,col in enumerate(frame.columns,1):
            ws.write(4,c,str(col)+( " · Forecast" if forecast else " · Actual"),forecast_header if forecast else header)
        for row,values in frame.iterrows():
            r = maps[name][row]
            ws.write(r,0,row,text_fmt)
            kind = metric_kind(row)
            for c,value in enumerate(values,1):
                write_numeric(ws,r,c,value,styles[kind,"input"],units.scale if kind in ("money","check") else 1)

    h = bundle.historical
    for name,frame in (("Historical IS",h.income),("Historical BS",h.balance),("Historical CF",h.cashflow)):
        table(name,frame)
    aw = sheets["Assumptions"]
    aw.write_row(4,0,["Editable model driver","Value","Basis"],header)
    amap = {}
    for n,(key,value) in enumerate(asdict(bundle.assumptions).items(),5):
        amap[key] = f"'Assumptions'!$B${n+1}"
        aw.write(n,0,LABELS[key],text_fmt)
        kind = "number" if key in ("dso","dio","dpo","beta") else "pct"
        aw.write(n,1,value,styles[kind,"edit"])
        aw.write(n,2,"Model assumption",note)
        bounds = (-.5,1) if key=="growth" else (-1,1) if key=="debt_change_pct" else (-.05,.10) if key=="terminal_growth" else (0,730) if key in ("dso","dio","dpo") else (0,5) if key=="beta" else (0,1)
        aw.data_validation(n,1,n,1,{"validate":"decimal","criteria":"between","minimum":bounds[0],"maximum":bounds[1],"error_type":"stop","error_message":"Use a value within the supported range."})
    f = bundle.forecasts.get("Base")
    val = bundle.valuations.get("Base")
    source_inputs = {"Market Cap":bundle.data.info.get("marketCap",np.nan),"Current Price":bundle.data.info.get("currentPrice",np.nan)}
    if f:
        source_inputs.update({f"Opening {key}":value for key,value in f.opening.items()})
    if val and val.values:
        source_inputs["Minority Interest"] = val.values.get("Minority Interest")
        source_inputs["Preferred Equity"] = val.values.get("Preferred Equity")
    n = 7+len(amap)
    for key,value in source_inputs.items():
        amap[key] = f"'Assumptions'!$B${n+1}"
        aw.write(n,0,key,text_fmt)
        raw_key = key.removeprefix("Opening ")
        kind = metric_kind(raw_key)
        write_numeric(aw,n,1,value,styles[kind,"input"],units.scale if kind in ("money","check") else 1)
        aw.write(n,2,"Source / disclosed opening normalization",note)
        n += 1
    aw.set_column(0,0,44)
    aw.set_column(2,2,46)

    def ref(sheet,row,col):
        return f"'{sheet}'!{xl_rowcol_to_cell(maps[sheet][row],col)}"

    def formula(sheet,row,col,expr,value=None):
        kind = metric_kind(row)
        if value is None:
            value = frame_lookup[sheet].loc[row].iloc[col-1]
            value = excel_number(value,units.scale if kind in ("money","check") else 1)
        write_cached_formula(sheets[sheet],maps[sheet][row],col,"="+expr,styles[kind,"link" if "!" in expr else "formula"],value)

    if f:
        for name,frame in (("Forecast IS",f.income),("Forecast BS",f.balance),("Forecast CF",f.cashflow)):
            table(name,frame,True)
        for name in ("Revenue Build","Working Capital","Capex & Depreciation","Debt Schedule"):
            table(name,f.schedules[name],True)
        for c in range(1,len(f.income.columns)+1):
            I = lambda row:ref("Forecast IS",row,c)
            B = lambda row:ref("Forecast BS",row,c)
            C = lambda row:ref("Forecast CF",row,c)
            D = lambda row:ref("Debt Schedule",row,c)
            W = lambda row:ref("Working Capital",row,c)
            P = lambda row:ref("Forecast BS",row,c-1) if c>1 else amap["Opening "+row]
            A = lambda key:amap[key]
            previous_revenue = ref("Forecast IS","Revenue",c-1) if c>1 else A("Opening Revenue")
            is_expr = {
                "Revenue":f"{previous_revenue}*(1+{A('growth')})", "COGS":f"{I('Revenue')}*(1-{A('gross_margin')})",
                "Gross Profit":f"{I('Revenue')}-{I('COGS')}", "EBITDA":f"{I('Revenue')}*{A('ebitda_margin')}",
                "D&A":f"MIN({I('Revenue')}*{A('da_pct')},MAX(0,{P('Net PPE')}+{C('Capex')}))",
                "EBIT":f"{I('EBITDA')}-{I('D&A')}", "Operating Expenses":f"{I('Gross Profit')}-{I('EBIT')}",
                "Interest Expense":f"{P('Debt')}*{A('interest_rate')}", "Pretax Income":f"{I('EBIT')}-{I('Interest Expense')}",
                "Taxes":f"MAX(0,{I('Pretax Income')})*{A('tax_rate')}", "Net Income":f"{I('Pretax Income')}-{I('Taxes')}",
                "EPS":f'IF(ISNUMBER({A("Opening Shares")}),{I("Net Income")}*{units.scale}/{A("Opening Shares")},"N/A")',
            }
            for row,expr in is_expr.items():
                formula("Forecast IS",row,c,expr)
            wc_expr = {"Accounts Receivable":f"{I('Revenue')}*{A('dso')}/365","Inventory":f"{I('COGS')}*{A('dio')}/365",
                       "Accounts Payable":f"{I('COGS')}*{A('dpo')}/365"}
            for row,expr in wc_expr.items():
                formula("Working Capital",row,c,expr)
            nwc_expr = f"{W('Accounts Receivable')}+{W('Inventory')}+{A('Opening Other Current Assets')}-{W('Accounts Payable')}-{A('Opening Other Current Liabilities')}"
            formula("Working Capital","Net Working Capital",c,nwc_expr)
            prev_nwc = ref("Working Capital","Net Working Capital",c-1) if c>1 else A("Opening Net Working Capital")
            formula("Working Capital","Change in Working Capital",c,f"{W('Net Working Capital')}-{prev_nwc}")
            for row,key in (("Receivable days","dso"),("Inventory days","dio"),("Payable days","dpo")):
                formula("Working Capital",row,c,A(key))
            cf_expr = {"Net Income":I("Net Income"),"D&A":I("D&A"),"Change in Working Capital":W("Change in Working Capital"),
                "CFO":f"{C('Net Income')}+{C('D&A')}-{C('Change in Working Capital')}","Capex":f"{I('Revenue')}*{A('capex_pct')}",
                "FCF":f"{C('CFO')}-{C('Capex')}","Planned Debt Change":D("Planned Debt Change"),"Funding Draw":D("Funding Draw"),
                "Dividends":f"MAX(0,{I('Net Income')})*{A('dividend_payout')}",
                "Financing Cash Flow":f"{C('Planned Debt Change')}+{C('Funding Draw')}-{C('Dividends')}",
                "Net Cash Change":f"{C('FCF')}+{C('Financing Cash Flow')}","Opening Cash":P("Cash"),
                "Closing Cash":f"{C('Opening Cash')}+{C('Net Cash Change')}","Cash Reconciliation":f"{B('Cash')}-{C('Opening Cash')}-{C('Net Cash Change')}",
                "UFCF":f"{I('EBIT')}-MAX(0,{I('EBIT')})*{A('tax_rate')}+{I('D&A')}-{C('Capex')}-{W('Change in Working Capital')}",
            }
            for row,expr in cf_expr.items():
                formula("Forecast CF",row,c,expr)
            debt_expr = {"Opening Debt":P("Debt"),"Planned Debt Change":f"MAX(-{P('Debt')},{P('Debt')}*{A('debt_change_pct')})",
                "Funding Draw":f"MAX(0,{I('Revenue')}*{A('min_cash_pct')}-({C('Opening Cash')}+{C('FCF')}+{D('Planned Debt Change')}-{C('Dividends')}))",
                "Debt":f"{D('Opening Debt')}+{D('Planned Debt Change')}+{D('Funding Draw')}","Interest rate":A("interest_rate"),"Interest Expense":I("Interest Expense")}
            for row,expr in debt_expr.items():
                formula("Debt Schedule",row,c,expr)
            bs_expr = {"Cash":C("Closing Cash"),"Accounts Receivable":W("Accounts Receivable"),"Inventory":W("Inventory"),"Accounts Payable":W("Accounts Payable"),
                "Current Assets":f"{B('Cash')}+{B('Accounts Receivable')}+{B('Inventory')}+{B('Other Current Assets')}",
                "Net PPE":f"{P('Net PPE')}+{C('Capex')}-{I('D&A')}","Total Assets":f"{B('Current Assets')}+{B('Net PPE')}+{B('Other Assets')}",
                "Debt":D("Debt"),"Current Debt":f"{D('Debt')}*IF({A('Opening Debt')}>0,MAX(0,MIN(1,{A('Opening Current Debt')}/{A('Opening Debt')})),0)",
                "Long Term Debt":f"{B('Debt')}-{B('Current Debt')}","Current Liabilities":f"{B('Accounts Payable')}+{B('Other Current Liabilities')}+{B('Current Debt')}",
                "Total Liabilities":f"{B('Current Liabilities')}+{B('Long Term Debt')}+{B('Other Liabilities')}",
                "Equity":f"{P('Equity')}+{I('Net Income')}-{C('Dividends')}","Total Liabilities + Equity":f"{B('Total Liabilities')}+{B('Equity')}",
                "Balance Check":f"{B('Total Assets')}-{B('Total Liabilities + Equity')}"}
            for row in ("Other Current Assets","Other Assets","Other Current Liabilities","Other Liabilities"):
                bs_expr[row] = A("Opening "+row)
            for row,expr in bs_expr.items():
                formula("Forecast BS",row,c,expr)
            for row in f.schedules["Revenue Build"].index:
                expr = A({"Revenue growth":"growth","Gross margin":"gross_margin","EBITDA margin":"ebitda_margin"}[row]) if row in ("Revenue growth","Gross margin","EBITDA margin") else I(row)
                formula("Revenue Build",row,c,expr)
            for row,expr in {"Opening Net PPE":P("Net PPE"),"Capex":C("Capex"),"D&A":I("D&A"),"Net PPE":B("Net PPE")}.items():
                formula("Capex & Depreciation",row,c,expr)
    if val and val.values:
        v = val.values
        dcf_rows = ["Current Price","Implied Price","Upside","WACC","Terminal Growth","PV Forecast FCF","PV Terminal Value","Enterprise Value","Net Debt","Minority Interest","Preferred Equity","Equity Value","Cost of Equity","After-tax Cost of Debt","Debt Weight"]
        maps["DCF"] = {row:n+5 for n,row in enumerate(dcf_rows)}
        dw = sheets["DCF"]
        dw.write_row(4,0,["Valuation bridge","Base value"],header)
        for row in dcf_rows:
            dw.write(maps["DCF"][row],0,row,text_fmt)
        V = lambda row:ref("DCF",row,1)
        A = lambda key:amap[key]
        years = len(f.income.columns)
        flows = [ref("Forecast CF","UFCF",c) for c in range(1,years+1)]
        exprs = {"Current Price":A("Current Price"),"Cost of Equity":f"{A('risk_free')}+{A('beta')}*{A('equity_premium')}",
            "After-tax Cost of Debt":f"{A('cost_debt')}*(1-{A('tax_rate')})","Debt Weight":f"{A('Opening Debt')}/({A('Market Cap')}+{A('Opening Debt')})",
            "WACC":f"{V('Cost of Equity')}*(1-{V('Debt Weight')})+{V('After-tax Cost of Debt')}*{V('Debt Weight')}","Terminal Growth":A("terminal_growth"),
            "PV Forecast FCF":"+".join(f"{flow}/(1+{V('WACC')})^{n}" for n,flow in enumerate(flows,1)),
            "PV Terminal Value":f'IF(AND({V("WACC")}>{V("Terminal Growth")},{flows[-1]}>0),{flows[-1]}*(1+{V("Terminal Growth")})/({V("WACC")}-{V("Terminal Growth")})/(1+{V("WACC")})^{years},"N/A")',
            "Enterprise Value":f'IF(ISNUMBER({V("PV Terminal Value")}),{V("PV Forecast FCF")}+{V("PV Terminal Value")},"N/A")',
            "Net Debt":f"{A('Opening Debt')}-{A('Opening Cash')}","Minority Interest":A("Minority Interest"),"Preferred Equity":A("Preferred Equity"),
            "Equity Value":f'IF(ISNUMBER({V("Enterprise Value")}),{V("Enterprise Value")}-{V("Net Debt")}-{V("Minority Interest")}-{V("Preferred Equity")},"N/A")',
            "Implied Price":f'IF(AND(ISNUMBER({V("Equity Value")}),ISNUMBER({A("Opening Shares")})),{V("Equity Value")}*{units.scale}/{A("Opening Shares")},"N/A")',
            "Upside":f'IF(AND(ISNUMBER({V("Implied Price")}),ISNUMBER({V("Current Price")}),{V("Current Price")}>0),{V("Implied Price")}/{V("Current Price")}-1,"N/A")'}
        for row,expr in exprs.items():
            kind = "pct" if row in ("Upside","WACC","Terminal Growth","Cost of Equity","After-tax Cost of Debt","Debt Weight") else metric_kind(row)
            value = excel_number(v.get(row),units.scale if kind=="money" else 1)
            write_cached_formula(dw,maps["DCF"][row],1,"="+expr,styles[kind,"link"],value)
        sw = sheets["Sensitivity"]
        sw.write(4,0,"WACC / terminal growth",header)
        for c,delta in enumerate(np.linspace(-.01,.01,5),1):
            write_cached_formula(sw,4,c,f"={V('Terminal Growth')}+({delta})",styles["pct","link"],as_float(v.get("Terminal Growth"))+delta)
        for r,delta in enumerate(np.linspace(-.02,.02,5),5):
            write_cached_formula(sw,r,0,f"={V('WACC')}+({delta})",styles["pct","link"],as_float(v.get("WACC"))+delta)
            for c in range(1,6):
                rate = xl_rowcol_to_cell(r,0,col_abs=True)
                growth = xl_rowcol_to_cell(4,c,row_abs=True)
                pv = "+".join(f"{flow}/(1+{rate})^{n}" for n,flow in enumerate(flows,1))
                expr = f'IF(AND({rate}>{growth},{rate}>0,ISNUMBER({A("Opening Shares")})),(({pv})+{flows[-1]}*(1+{growth})/({rate}-{growth})/(1+{rate})^{years}-{V("Net Debt")}-{V("Minority Interest")}-{V("Preferred Equity")})*{units.scale}/{A("Opening Shares")},"N/A")'
                cached = val.sensitivity.iloc[r-5,c-1] if val.sensitivity.shape == (5,5) else np.nan
                write_cached_formula(sw,r,c,"="+expr,styles["price","link"],cached)
        sw.conditional_format(5,1,9,5,{"type":"3_color_scale","min_color":"#f5d4cf","mid_color":"#ffffff","max_color":"#8ed2c4"})
    else:
        sheets["DCF"].write(5,0,val.message if val else "Valuation unavailable",note)
    # KPI and multi-case comparison are explicitly captured app outputs, separate from the editable Base workbook model.
    kw = sheets["KPIs"]
    kw.write(2,0,"Captured app KPIs. Regenerate the export after changing assumptions in the app; this table does not recalculate on Excel edits.",note)
    kw.write(4,0,"KPI",header)
    for c,col in enumerate(bundle.kpis.columns,1):
        kw.write(4,c,col+(" · Actual" if col in h.years else " · Base Forecast"),header if col in h.years else forecast_header)
    for r,(row,values) in enumerate(bundle.kpis.iterrows(),5):
        kw.write(r,0,row,text_fmt)
        kind = "pct" if row in PERCENT_KPIS else "number" if row in DAY_KPIS else "multiple"
        for c,value in enumerate(values,1):
            kw.write(r,c,value if finite(value) else "N/A",styles[kind,"input"])
    scenario = sheets["Scenario Analysis"]
    scenario.write(2,0,"Captured Bear / Base / Bull app results. Refresh by regenerating the workbook; scenario comparison is not recalculated by Excel edits.",note)
    scenario.write_row(4,0,["Scenario","Revenue growth","EBITDA margin","Final revenue","DCF price"],header)
    for r,(name,model) in enumerate(bundle.forecasts.items(),5):
        value = bundle.valuations[name].values.get("Implied Price",np.nan)
        scenario.write(r,0,name,text_fmt)
        for c,x,kind in [(1,model.assumptions.growth,"pct"),(2,model.assumptions.ebitda_margin,"pct"),(3,model.income.iloc[:,-1]["Revenue"]/units.scale,"money"),(4,value,"price")]:
            scenario.write(r,c,x if finite(x) else "N/A",styles[kind,"input"])
    cw = sheets["Comps"]
    cw.write(2,0,"Captured Yahoo trailing metrics. Monetary figures use the selected scale in each row's native currency. Multiples are not meaningful for non-positive denominators.",note)
    if comps is not None and not comps.empty:
        cw.write_row(4,0,list(comps.columns),header)
        for r,(_,row) in enumerate(comps.iterrows(),5):
            for c,(key,value) in enumerate(row.items()):
                if key in ("Market Cap","EV","Revenue","EBITDA","Net Income"):
                    cw.write(r,c,value/units.scale if finite(value) else "N/A",styles["money","input"])
                elif key in ("Revenue Growth","EBITDA Margin","EV / Revenue","EV / EBITDA","P/E"):
                    cw.write(r,c,value if finite(value) else "N/A",styles["pct" if "Growth" in key or "Margin" in key else "multiple","input"])
                else:
                    cw.write(r,c,str(value),text_fmt)
    else:
        cw.write(5,0,"No peer tickers supplied or no peer data available.",note)
    checks = sheets["Model Checks"]
    checks.write_row(4,0,["Check","Status","Detail"],header)
    checks.set_column(2,2,86)
    for r,(_,row) in enumerate(bundle.checks.iterrows(),5):
        checks.write_row(r,0,row.tolist(),note)
        checks.set_row(r,36)
        if f and row["Check"] in ("Forecast balance sheet","Cash flow reconciliation"):
            sheet,key = ("Forecast BS","Balance Check") if row["Check"]=="Forecast balance sheet" else ("Forecast CF","Cash Reconciliation")
            condition = ",".join(f"ABS({ref(sheet,key,c)})<={1/units.scale}" for c in range(1,len(f.income.columns)+1))
            checks.write_formula(r,1,f'=IF(AND({condition}),"PASS","FAIL")',text_fmt,row["Status"])
        elif val and val.values and row["Check"]=="Terminal growth below WACC":
            checks.write_formula(r,1,f'=IF({ref("DCF","WACC",1)}>{ref("DCF","Terminal Growth",1)},"PASS","FAIL")',text_fmt,row["Status"])
    checks.conditional_format(5,1,5+len(bundle.checks),1,{"type":"text","criteria":"containing","value":"FAIL","format":wb.add_format({"bg_color":"#fce4d6","font_color":"#9c0006"})})
    dash = sheets["Dashboard"]
    if f:
        dashboard = pd.concat([h.income.loc[["Revenue","EBITDA","Net Income"]],f.income.loc[["Revenue","EBITDA","Net Income"]]],axis=1)
        table("Dashboard",dashboard)
        for c,col in enumerate(dashboard.columns,1):
            actual = col in h.years
            source_col = h.years.index(col)+1 if actual else list(f.income.columns).index(col)+1
            dash.write(4,c,col+(" · Actual" if actual else " · Forecast"),header if actual else forecast_header)
            for row in dashboard.index:
                formula("Dashboard",row,c,ref("Historical IS" if actual else "Forecast IS",row,source_col))
        chart = wb.add_chart({"type":"column"})
        for r,color in zip(range(5,8),("#172b4d","#087f8c","#b38b4d")):
            chart.add_series({"name":["Dashboard",r,0],"categories":["Dashboard",4,1,4,len(dashboard.columns)],"values":["Dashboard",r,1,r,len(dashboard.columns)],"fill":{"color":color},"border":{"none":True}})
        chart.set_title({"name":"Operating performance | Actual & Base Forecast"})
        chart.set_y_axis({"name":units.label,"num_format":"#,##0"})
        chart.set_legend({"position":"bottom"})
        chart.set_size({"width":1050,"height":420})
        dash.insert_chart("A11",chart)
    cover = sheets["Cover"]
    cover.write(5,0,bundle.data.name,title)
    cover.write(7,0,"Financial modelling & valuation",text_fmt)
    cover.write(9,0,"Source retrieved (UTC)",text_fmt)
    cover.write(9,1,bundle.data.retrieved_at,note)
    cover.set_row(9,36)
    cover.merge_range(11,0,12,6,"Blue: hardcoded inputs | Green: links | Black: formulas | Yellow: editable assumptions. Forecast statements and DCF recalculate. KPIs, scenarios, comps and source checks are captured outputs; regenerate these in the app.",note)
    sources = sheets["Sources"]
    sources.set_column(0,0,36)
    sources.set_column(1,1,110)
    source_rows = [("Provider",bundle.data.source),("Company",f"https://finance.yahoo.com/quote/{bundle.data.ticker}/financials/"),
                   ("Retrieved UTC",bundle.data.retrieved_at),("Financial basis","Annual fiscal statements; market price and shares are current at retrieval. DCF discounting begins at the latest fiscal period and uses year-end cash flows; it is not a stub-period valuation as of today."),
                   ("WACC","CAPM cost of equity; current market capitalization; latest reported book debt as a proxy for market-value debt."),
                   ("Equity bridge","Latest annual cash and debt; disclosed minority / preferred balances deducted when available. No FX conversion."),
                   ("Defaults","Historical operating ratios are bounded; risk-free rates, equity risk premium and financing rates are illustrative editable inputs, not live market yields.")]
    source_rows += [("Disclosure",x) for x in bundle.data.warnings+bundle.notices+h.notes+(f.notes if f else [])]
    sources.write_row(4,0,["Source / method","Details"],header)
    for r,row in enumerate(source_rows,5):
        sources.write_row(r,0,row,note)
        sources.set_row(r,66)
    wb.close()
    return out.getvalue()


POWERBI_README = """FinModel AI — Power BI import guide

Import each CSV using UTF-8. No ZIP is required. Monetary values are UNSCALED
in each company's reporting currency. EPS and price are per share, percentages
are decimals, ratios are multiples, and day metrics are days. No FX conversion.
Empty numeric fields are missing, never a fabricated zero.

Relationships (single direction, one-to-many):
Company[CompanyID] -> all fact tables[CompanyID].
Periods[PeriodID] -> FinancialActuals, Forecasts, KPIs[PeriodID].
Periods is unique on fiscal period-end date. PeriodID is an ISO date string;
PeriodEnd should be a Date. Set CompanyID, Metric, Statement, Scenario, Status
and Classification as Text, Value as Decimal Number, IsForecast as Boolean.
Company is unique on ticker. Select ONE company, metric, statement and scenario
before aggregating. FinancialActuals / Forecasts are long-form facts; income,
balance sheet and cash flow metrics may share names, so filter Statement too.
KPIs contains actual and Base model forecast metrics with Classification labels.
Valuation and Assumptions are scenario facts, not period facts.

Suggested DAX measures:
Actual Revenue = CALCULATE(SUM(FinancialActuals[Value]),
    FinancialActuals[Metric] = "Revenue", FinancialActuals[Statement] = "Income Statement")
Base Forecast Revenue = CALCULATE(SUM(Forecasts[Value]),
    Forecasts[Metric] = "Revenue", Forecasts[Statement] = "Income Statement",
    Forecasts[Scenario] = "Base")
Revenue Crore = DIVIDE([Actual Revenue], 10000000)
DCF Price = CALCULATE(MAX(Valuation[Value]), Valuation[Metric] = "Implied Price",
    Valuation[Scenario] = "Base")

Do not sum stock balances across periods or sum ratios and per-share values.
Use ending balances for balance-sheet metrics and recompute margins from their
underlying flows. Use a fiscal date dimension for time intelligence.
Suggested pages: Executive, Historical vs Forecast, Scenario Valuation, Risks.
Refresh by importing a new matching set of CSV files from the app. Estimate
data from Yahoo is displayed separately in the Consensus tab.
"""


def powerbi_files(bundle):
    data,h = bundle.data,bundle.historical
    ticker = data.ticker
    base = bundle.forecasts.get("Base")
    future = list(base.income.columns) if base else []
    company = pd.DataFrame([{"CompanyID":ticker,"CompanyName":data.name,"Currency":data.currency,"Sector":data.info.get("sector",""),"Source":data.source,"RetrievedAt":data.retrieved_at}])
    periods = pd.DataFrame([{"PeriodID":d,"PeriodEnd":d,"FiscalYear":int(d[:4]),"IsForecast":d in future} for d in h.years+future])
    def facts(model,scenario,classification):
        rows = []
        for key,label in (("income","Income Statement"),("balance","Balance Sheet"),("cashflow","Cash Flow")):
            for metric,values in getattr(model,key).iterrows():
                for period,value in values.items():
                    rows.append({"CompanyID":ticker,"PeriodID":period,"Statement":label,"Metric":metric,"Value":value,"Currency":data.currency,"Scenario":scenario,"Classification":classification,"Unit":"per share" if metric=="EPS" else "currency absolute"})
        return rows
    actuals = pd.DataFrame(facts(h,"Actual","Actual"))
    forecasts = pd.DataFrame([r for name,model in bundle.forecasts.items() for r in facts(model,name,"Model Forecast")],columns=actuals.columns)
    kpis = pd.DataFrame([{"CompanyID":ticker,"PeriodID":period,"Metric":metric,"Value":value,"Classification":"Actual" if period in h.years else "Model Forecast","Scenario":"Actual" if period in h.years else "Base","Unit":"decimal rate" if metric in PERCENT_KPIS else "days" if metric in DAY_KPIS else "multiple"} for metric,values in bundle.kpis.iterrows() for period,value in values.items()])
    vals = pd.DataFrame([{"CompanyID":ticker,"Scenario":name,"Metric":metric,"Value":value,"Currency":data.currency,"Unit":"per share" if metric in ("Current Price","Implied Price") else "decimal rate" if metric in ("WACC","Terminal Growth","Terminal Value Weight","Cost of Equity","After-tax Cost of Debt","Debt Weight","Upside") else "currency absolute"} for name,v in bundle.valuations.items() for metric,value in v.values.items()],columns=["CompanyID","Scenario","Metric","Value","Currency","Unit"])
    assumptions = pd.DataFrame([{"CompanyID":ticker,"Scenario":name,"Assumption":LABELS[key],"Value":value} for name,model in bundle.forecasts.items() for key,value in asdict(model.assumptions).items()],columns=["CompanyID","Scenario","Assumption","Value"])
    checks = bundle.checks.copy()
    checks.insert(0,"CompanyID",ticker)
    frames = {"Company":company,"Periods":periods,"FinancialActuals":actuals,"Forecasts":forecasts,"KPIs":kpis,"Valuation":vals,"Assumptions":assumptions,"ModelChecks":checks}
    return {**{f"{name}.csv":frame.to_csv(index=False).encode("utf-8-sig") for name,frame in frames.items()},"PowerBI_README.txt":POWERBI_README.encode("utf-8")}
