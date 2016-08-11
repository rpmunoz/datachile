"""
Access the visualization by clicking on the HTML file in the Files tab.

Bokeh is a fantastic interactive visualization library. Check it out here:
http://bokeh.pydata.org/en/latest/

I'm happy to answer any questions you may have, just leave a comment. Feel free to share any ideas or thoughts you have
as well. I'd especially love to see what other kinds of visualizations you guys can come up with using Bokeh!
"""

import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz
import re, unicodedata, datetime

from bokeh.models import CustomJS, ColumnDataSource, Div, Paragraph, Select, HoverTool, BoxZoomTool, ResetTool,\
    DatetimeTickFormatter, HBox, VBox
from bokeh.plotting import Figure, output_file, save, show


def create_cds_key(s):
    """ColumnDataSource keys can't have special chars in them"""
    s = s.replace('-', '_')
    s = s.replace(' ', '_')
    s = s.replace('(', '')
    s = s.replace(')', '')
    s = s.replace("'", '')
    s = s.replace('.', '')
    s = s.replace(',', '')
    s = s.lower()
    return s

# mode=inline bundles the bokeh js and css in the html rather than accessing the cdn
# this is handy since kaggle scripts can't access internet resources
output_file('display_fondecyt_regular.html', title='Centro de Estudios ANIP')

# Read Mineduc data
mineduc_file='data/Mineduc Listado IES Vigentes 05-2016.csv'
mineduc=pd.read_csv(mineduc_file, header=0, sep=',')
mineduc['fecha_reconocimiento']=pd.to_datetime(mineduc['fecha_reconocimiento'])
mineduc['año_reconocimiento']=mineduc['fecha_reconocimiento'].dt.year

for i in range(len(mineduc.index)):
    old=mineduc.loc[i,'nombre']
    new=re.sub(" ?\(\+\+\) ?| ?\(\*.*\) ?","", old)
    mineduc.loc[i,'nombre']=new

mineduc=mineduc.sort_values('fecha_reconocimiento').reset_index(drop=True)

# Read the Fondecyt regular data
fondecyt_2010=pd.read_csv('data/fondecyt regular 2010.csv', header=0, sep=',')
fondecyt_2011=pd.read_csv('data/fondecyt regular 2011.csv', header=0, sep=',')
fondecyt_2012=pd.read_csv('data/fondecyt regular 2012.csv', header=0, sep=',')
fondecyt_2013=pd.read_csv('data/fondecyt regular 2013.csv', header=0, sep=',')
fondecyt_2014=pd.read_csv('data/fondecyt regular 2014.csv', header=0, sep=',')
fondecyt_2015=pd.read_csv('data/fondecyt regular 2015.csv', header=0, sep=',')
fondecyt_2016=pd.read_csv('data/fondecyt regular 2016.csv', header=0, sep=',')

fondecyt=pd.concat([fondecyt_2010,fondecyt_2011,fondecyt_2012,fondecyt_2013,fondecyt_2014,fondecyt_2015,fondecyt_2016]).reset_index(drop=True)
for i in range(len(fondecyt.index)):
    name=(fondecyt.loc[i,'nombre']).upper()
    name=name.replace("UNIV.","UNIVERSIDAD").replace("PONT.","PONTIFICIA").replace("CS.","CIENCIAS").replace("TEC.","TECNOLOGIA")
    name=name.replace("INTERNACIONAL SEK","SEK").replace("UNIVERSIDAD CIENCIAS DE LA INFORMATICA","UNIVERSIDAD UCINF")
    fondecyt.loc[i,'nombre']=name.capitalize()

for i in range(len(fondecyt.index)):
    if fondecyt.ix[i,'nombre'] != 'Otras universidades':
        d = mineduc.apply(lambda x: fuzz.ratio(x['nombre'].upper(), fondecyt.ix[i, 'nombre'].upper()), axis=1)
        if d.max()<85:
            print("WARNING - Fuzz ratio lower than 85")
            print('Fondecyt name: ', fondecyt.ix[i,'nombre'])
            print('Mineduc name: ', mineduc.ix[d.idxmax(), 'nombre'])
        fondecyt.ix[i,'nombre']=mineduc.ix[d.idxmax(), 'nombre']

fondecyt=fondecyt.rename(columns = {'n_concursados':'Concursados', 'n_aprobados':'Adjudicados'})
fondecyt['Tasa de adjudicacion']=np.round(fondecyt['Adjudicados']/fondecyt['Concursados']*100,decimals=1)

data=fondecyt.copy()
data=pd.melt(fondecyt, id_vars=['nombre','año'], var_name='categoria', value_name='valor').fillna(0)
data['nombre']=data.apply(lambda x: unicodedata.normalize('NFD', x['nombre']).encode('ascii', 'ignore').decode("utf-8").replace('-', '_').replace("'", '').replace(',', ''), axis=1)
data_nombre_unique=data.query("categoria == 'Adjudicados'").groupby('nombre').sum().sort_values('valor', ascending=False).index.values
#data['categoria']=data.apply(lambda x: x['nombre']+'_'+x['categoria'], axis=1)
data['dt']=pd.to_datetime(data['año'], format='%Y')


# read the data
#data = pd.read_csv('data/GlobalLandTemperaturesByState.csv', parse_dates=['dt'])

# date range which will be used to give all dataframes a common index
dr = pd.date_range(start='2010', end='2016', freq='AS')

# dict to hold bokeh model objects which can be passed to CustomJS
plot_sources = dict()

#
countries = list(data_nombre_unique)
for country in countries:
    country_data = data.loc[data['nombre'] == country]
    country_states = list(country_data['categoria'].unique())
    state_select = Select(value=country_states[0], title='Categoria de proyecto', options=country_states)

    country_key = create_cds_key(country)
    plot_sources[country_key] = state_select

    # create a ColumnDataSource for each state in country
    for state in country_states:
        state_data = country_data.loc[country_data['categoria'] == state]
        state_data = state_data.drop(['nombre', 'categoria', 'año'], axis=1)
        state_data = state_data.set_index('dt')
        state_data = state_data.reindex(dr).fillna(0.)
        state_data.index.name = 'dt'

        state_key = create_cds_key(country)+'_'+create_cds_key(state)
        plot_sources[state_key] = ColumnDataSource(state_data)


# create a ColumnDataSource to use for the actual plot, default on Oregon, United States
plot_data = data.loc[(data['nombre'] == 'Universidad de Chile') & (data['categoria'] == 'Concursados')]
plot_data = plot_data.drop(['nombre', 'categoria', 'año'], axis=1)
plot_data['dt_formatted'] = plot_data['dt'].apply(lambda x: x.strftime('%Y'))
plot_data = plot_data.set_index('dt')
plot_data = plot_data.reindex(dr).fillna(0.)
plot_data.index.name = 'dt'
plot_sources['plot_source'] = ColumnDataSource(plot_data)

# configure HoverTool
hover = HoverTool(
#        tooltips=[
#            ("Año", "@dt_formatted"),
#            ("Valor", "@valor"),
#        ],
        tooltips="""
            <div style="background: #FFFFFF;">
                <span style="font-size: 20px;">Año: @dt_formatted</span><br />
                <span style="font-size: 18px; color: black;">Valor: @valor{1.1}</span>
            </div>
        """,
        names=["circle"]
    )

# setup some basic tools for the plot interactions
TOOLS = [BoxZoomTool(), hover, ResetTool()]

# define our plot and set various plot components
plot = Figure(plot_width=700, x_axis_type='datetime', title='Proyectos Fondecyt regular', x_range=(datetime.date(2009,9,1),datetime.date(2016,6,1)), tools=TOOLS)
plot.circle('dt', 'valor', source=plot_sources['plot_source'], size=10, name="circle")
plot.line('dt', 'valor', source=plot_sources['plot_source'], line_width=3, line_alpha=0.6, name="line")
plot.xaxis.axis_label = "Año"
plot.yaxis.axis_label = "Número de proyectos"
plot.axis.axis_label_text_font_size = "12pt"
plot.axis.axis_label_text_font_style = "bold"
plot.xaxis[0].formatter = DatetimeTickFormatter(formats=dict(months=["%b %Y"], years=["%Y"]))
plot.title.align='center'
plot.title.text_font='Roboto'
plot.title.text_font_size='16pt'
plot.title.text_alpha=0.7

# add the plot and yaxis to our sources dict so we can manipulate various properties via javascript
plot_sources['plot'] = plot
plot_sources['yaxis_label'] = plot.yaxis[0]


# callback when a new state is selected
states_callback = CustomJS(args=plot_sources, code="""
        var state = cb_obj.get('value');
        var countries = {'Universidad de Chile': eval('universidad_de_chile'),
                         'Pontificia Universidad Catolica de Chile': eval('pontificia_universidad_catolica_de_chile'),
                         'Universidad de Concepcion': eval('universidad_de_concepcion'),
                         'Universidad de Santiago de Chile': eval('universidad_de_santiago_de_chile'),
                         'Universidad Austral de Chile': eval('universidad_austral_de_chile'),
                         'Pontificia Universidad Catolica de Valparaiso': eval('pontificia_universidad_catolica_de_valparaiso'),
                         'Universidad Tecnica Federico Santa Maria': eval('universidad_tecnica_federico_santa_maria'),
                         'Universidad Andres Bello': eval('universidad_andres_bello'),
                         'Universidad de Talca': eval('universidad_de_talca'),
                         'Universidad de La Frontera': eval('universidad_de_la_frontera'),
                         'Universidad de Valparaiso': eval('universidad_de_valparaiso'),
                         'Universidad Diego Portales': eval('universidad_diego_portales'),
                         'Universidad del Bio_Bio': eval('universidad_del_bio_bio'),
                         'Universidad Catolica del Norte': eval('universidad_catolica_del_norte'),
                         'Universidad de Los Andes': eval('universidad_de_los_andes'),
                         'Universidad Catolica de la Santisima Concepcion': eval('universidad_catolica_de_la_santisima_concepcion'),
                         'Universidad Alberto Hurtado': eval('universidad_alberto_hurtado'),
                         'Universidad Catolica de Temuco': eval('universidad_catolica_de_temuco'),
                         'Universidad Catolica del Maule': eval('universidad_catolica_del_maule'),
                         'Universidad de Tarapaca': eval('universidad_de_tarapaca'),
                         'Universidad Adolfo Ibanez': eval('universidad_adolfo_ibanez'),
                         'Universidad de Los Lagos': eval('universidad_de_los_lagos'),
                         'Universidad San Sebastian': eval('universidad_san_sebastian'),
                         'Universidad de Antofagasta': eval('universidad_de_antofagasta'),
                         'Universidad de La Serena': eval('universidad_de_la_serena'),
                         'Universidad del Desarrollo': eval('universidad_del_desarrollo'),
                         'Universidad Central de Chile': eval('universidad_central_de_chile'),
                         'Universidad de Vina del Mar': eval('universidad_de_vina_del_mar'),
                         'Universidad Academia de Humanismo Cristiano': eval('universidad_academia_de_humanismo_cristiano'),
                         'Universidad Tecnologica Metropolitana': eval('universidad_tecnologica_metropolitana'),
                         'Universidad de Magallanes': eval('universidad_de_magallanes'),
                         'Universidad Mayor': eval('universidad_mayor'),
                         'Universidad Arturo Prat': eval('universidad_arturo_prat'),
                         'Universidad Metropolitana de Ciencias de la Educacion': eval('universidad_metropolitana_de_ciencias_de_la_educacion'),
                         'Universidad del Pacifico': eval('universidad_del_pacifico'),
                         'Universidad Santo Tomas': eval('universidad_santo_tomas'),
                         'Universidad Autonoma de Chile': eval('universidad_autonoma_de_chile'),
                         'Universidad Finis Terrae': eval('universidad_finis_terrae'),
                         'Universidad Catolica Cardenal Raul Silva Henriquez': eval('universidad_catolica_cardenal_raul_silva_henriquez'),
                         'Universidad de Playa Ancha de Ciencias de la Educacion': eval('universidad_de_playa_ancha_de_ciencias_de_la_educacion'),
                         'Universidad Bernardo OHiggins': eval('universidad_bernardo_ohiggins'),
                         'Universidad de Arte y Ciencias Sociales ARCIS': eval('universidad_de_arte_y_ciencias_sociales_arcis'),
                         'Universidad de Atacama': eval('universidad_de_atacama'),
                         'Universidad Adventista de Chile': eval('universidad_adventista_de_chile'),
                         'Universidad de Las Americas': eval('universidad_de_las_americas'),
                         'Universidad UCINF': eval('universidad_ucinf'),
                         'Universidad Sek': eval('universidad_sek'),
                         'Universidad La Republica': eval('universidad_la_republica'),
                         'Universidad Iberoamericana de Ciencias y Tecnologia UNICIT': eval('universidad_iberoamericana_de_ciencias_y_tecnologia_unicit'),
                         'Universidad Gabriela Mistral': eval('universidad_gabriela_mistral'),
                         'Universidad Bolivariana': eval('universidad_bolivariana'),
                         'Universidad Pedro de Valdivia': eval('universidad_pedro_de_valdivia'),
                         'Otras universidades': eval('otras_universidades')};

        var country_title = '';
        Object.keys(countries).forEach( function (country) {
            if (countries[country].get('options').indexOf(state) >= 0) {
                country_title = country;
            }
        });

        plot.set('title', state + ', ' + country_title);

        var plot_data = plot_source.get('data');
        var country = country_select.get('value');

        var name_category = country.replace(/\s+/g, '_').toLowerCase()+'_'+state.replace(/\s+/g, '_').toLowerCase();
        var eval_str = name_category + ".get('data')"
        var new_data = eval(eval_str);

        plot_data['dt'] = []
        plot_data['valor'] = []

        for (i = 0; i < new_data['dt'].length; i++) {
            plot_data['dt'].push(new_data['dt'][i])
            plot_data['valor'].push(new_data['valor'][i])
        }

        if (state == 'Concursados') {
            yaxis_label.set('axis_label', 'Número de proyectos')
        } else if (state == 'Adjudicados') {
            yaxis_label.set('axis_label', 'Número de proyectos')
        } else if (state == 'Tasa de adjudicacion') {
            yaxis_label.set('axis_label', 'Porcentaje')
        }

        plot_source.trigger('change');
    """)


# widgets for more interactions
state_select = Select(value='Concursados', title='Categoria de Proyectos', options=plot_sources['universidad_de_chile'].options,
                      callback=states_callback)
plot_sources['state_select'] = state_select

# callback when a new country is selected
countries_callback = CustomJS(args=plot_sources, code="""
        var country = cb_obj.get('value');
        var country_title = cb_obj.get('value');
        country = country.replace(/\s+/g, '_').toLowerCase();

        var state = state_select.get('value');

        var plot_data = plot_source.get('data');

        var name_category = country.replace(/\s+/g, '_').toLowerCase()+'_'+state.replace(/\s+/g, '_').toLowerCase();
        var eval_str = name_category + ".get('data')"
        var new_data = eval(eval_str);

        plot_data['dt'] = []
        plot_data['valor'] = []

        for (i = 0; i < new_data['dt'].length; i++) {
            plot_data['dt'].push(new_data['dt'][i])
            plot_data['valor'].push(new_data['valor'][i])
        }

        if (state == 'Concursados') {
            yaxis_label.set('axis_label', 'Número de proyectos')
        } else if (state == 'Adjudicados') {
            yaxis_label.set('axis_label', 'Número de proyectos')
        } else if (state == 'Tasa de adjudicacion') {
            yaxis_label.set('axis_label', 'Porcentaje')
        }

        plot_source.trigger('change');
    """)

country_select = Select(value='Universidad de Chile', title='Nombre de Universidad', options=countries, callback=countries_callback)
states_callback.args['country_select'] = country_select

# paragraph widgets to add some text
p0 = Paragraph(text="")
p1 = Paragraph(text="Análisis descriptivo de los Proyectos Fondecyt regular en el período 2010-2016.")
p2 = Paragraph(text="Elija el nombre de la Universidad y luego la Cantidad que quiere visualizar.")
p3 = Paragraph(text="Para hacer zoom en una una zona del gráfico, haga click y dibuje un rectángulo.")
p4 = Paragraph(text="Ubique el mouse sobre los círculos para visualizar los valores.")
p5 = Div(text="""Desarrollado por <a href="http://twitter.com/robertopmunoz">@robertopmunoz</a>""")

# set the page layout
layout = HBox(VBox(country_select, state_select, p0, p1, p2, p3, p4, p5, width=380), plot, width=1100)
save(layout)
