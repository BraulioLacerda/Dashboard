#Bibliotecas
from shiny import App, render, ui, reactive
import pandas as pd
import plotnine as p9
from statsmodels.tsa.seasonal import STL

#Dados 
dados = (
    pd.read_csv("dados_tratados.csv", converters = {"Date": pd.to_datetime})
    .assign(indice = lambda x: x.Date)
    .set_index("indice")
    .asfreq("MS")
    )

#Front-end
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Diagnóstico da Inflação",
        ui.layout_sidebar(
            ui.sidebar(
                ui.markdown(
                    "Dashboar de Analise do IPCA brasileira"
                ),
                ui.input_select(
                    id = "indicador",
                    label= ui.strong("Indicador:"),
                    choices = dados.columns[1:].to_list(),
                    selected = "IPCA"
                ),
                ui.input_date_range(
                    id = "periodo",
                    label = ui.strong("Data inicial e final:"),
                    start = dados.Date.min().date(),
                    end = dados.Date.max().date(),
                    min = dados.Date.min().date(),
                    max = dados.Date.max().date(),
                    language = "pt-Br",
                    separator= " - "
                ),
                ui.input_numeric(
                    id = "ano",
                    label = ui.strong("Comparar com o ano:"),
                    value = dados.Date.max().year,
                    min = dados.Date.min().year,
                    max = dados.Date.max().year,
                    step = 1 
                ),
                ui.input_checkbox_group(
                    id = "componentes",
                    label = ui.strong("Componentes:"),
                    choices = ["% a.m", "Tendência", "Sazonalidade", "Média"],
                    selected = ["% a.m", "Tendência", "Média"]
                ),
                width = 275
            ), 
            ui.card(ui.output_plot("sazonal")),
            ui.card(ui.output_plot("decomposicao"))

        )
    ),
    bg = "green",
    inverse = True,
    title = "Analise Macro"
)
#Servidor
def server(input, output, session):

    @reactive.calc
    def dados_decomposicao():

        dt_inicial = input.periodo()[0]
        dt_final = input.periodo()[1]

        df =(
            dados
            .rename(columns = {input.indicador(): "indicador"})
            .query("Date >= @dt_inicial and Date <= @dt_final")
            .dropna()
            .filter(["Date","indicador"])
        )

        modelo = STL(df.indicador, robust = True).fit()

        comp = input.componentes()

        tabela = (
            pd.DataFrame(
                data = {
                    "Date": df.Date,
                    "% a.m" : df.indicador,
                    "Tendência" : modelo.trend,
                    "Sazonalidade" : modelo.seasonal,
                    "Média" : df.indicador.mean()
                },
                index = df.index
            )
            .melt(id_vars = "Date", var_name = "indicador", value_name = "valor" )
            .query("indicador in @comp" )
        )

        return tabela
    
        
    @render.plot
    def decomposicao():

        grafico = (
            p9.ggplot(dados_decomposicao()) +
            p9.aes(x = "Date" , y= "valor", color = "indicador") +
            p9.geom_line() +
            p9.labs(
                title = input.indicador() +  ": componentes da série",
                x = "",
                y = "",
                color = "",
                caption = "Dados: FGV/IBGE | Elaboração: LIMFIE",
            ) + 
            p9.theme(
                legend_position = "bottom"

            )

        )
        return grafico
    
    @reactive.calc
    def dados_sazonal():

        ano = input.ano()
        dt_inicial = input.periodo()[0]
        dt_final = input.periodo()[1]

        dados_ano = (
            dados
            .assign(
                mes = lambda x: pd.Categorical (
                    x.Date.dt.month_name(),
                    categories = x.Date.dt.month_name().unique(),
                    ) 
                )
            .query("Date.dt.year == @ano")
            .rename(columns = {input.indicador(): "indicador"})
            .filter(["mes","indicador"])
            .dropna()
            .set_index ("mes")
        )

        dados_estatistica = (
            dados
            .query ("Date >= @dt_inicial and Date <= @dt_final")
            .assign(
                mes = lambda x: pd.Categorical (
                    x.Date.dt.month_name(),
                    categories = x.Date.dt.month_name().unique(),
                    ) 
                )
            .rename(columns = {input.indicador(): "indicador"})
            .filter(["mes","indicador"])
            .groupby("mes")
            .indicador
            .agg(
                q25 = lambda x: x.quantile(0.25),
                Mediana = lambda x: x.median(),
                q75 = lambda x: x.quantile(0.75)
            )
        )

        df_sazonal = (
            dados_ano
            .join(dados_estatistica, how = "outer")
            .rename_axis("mes", axis = "index")
            .reset_index()
            .rename(columns = {"indicador": str(input.ano())})
            .melt(id_vars = ["mes", "q25", "q75"], var_name = "variavel", value_name = "valor")
        )

        return df_sazonal
    
    @render.plot
    def sazonal():

        grafico = (
            p9.ggplot(dados_sazonal())+
            p9.aes(
                x = "mes",
                y = "valor", 
                color = "variavel",
                group = "variavel",
                ymin = "q25",
                ymax = "q75"
                ) +
            p9.geom_ribbon(color = "none", fill = "black" , alpha = 0.25) +
            p9.geom_line(size = 1) +
            p9.labs(
                title = input.indicador() + ": padrão sazonal",
                subtitle = "Aréa sombreada = Intervalor interquantil",
                y = "",
                x = "",
                color = "",
                caption = "Dados: FGV/IBGE | Elaboração: LIMFIE",
                
            ) +
            p9.theme(
                legend_position = "bottom"
            )
        )
        return grafico


#Dashboard shiny
app = App(app_ui, server)
