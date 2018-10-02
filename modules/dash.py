import asyncio
import dash
import dash_core_components as dcc
import dash_html_components as html
import time
import threading
from collections import deque
import plotly.graph_objs as go
import utils


class LiveGraphs(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wss_pings = deque(maxlen=60)
        self.rtt_pings = deque(maxlen=60)
        self.times = deque(maxlen=60)

    def run(self):
        while True:
            app.run_server(host='10.1.73.87', port=6969)


lg = LiveGraphs()
# lg.start()


class _Discord(metaclass=utils.MetaCog, private=True, hidden=True):

    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.update_wsping())
        bot.loop.create_task(self.update_rttping())
        lg.start()

    async def update_wsping(self):
        while True:
            lg.wss_pings.append(self.bot.latency * 1000)
            await asyncio.sleep(1)

    async def update_rttping(self):
        await self.bot.wait_until_ready()

        while True:
            chan = self.bot.get_channel(434972274467274762)

            ts = time.time()
            msg = await chan.send('Ping!')
            rtt = (time.time() - ts) * 1000

            lg.rtt_pings.append(rtt)
            await msg.delete()

            await asyncio.sleep(1)


app = dash.Dash('Latency Over Time')
data_dict = {'WS Latency': lg.wss_pings, 'RTT': lg.rtt_pings}
app.layout = html.Div([
    html.Div([
        html.H2('Latency Over Time (Eviee)',
                style={'float': 'left',
                       }),
    ]),
    dcc.Dropdown(id='latency-name',
                 options=[{'label': s, 'value': s}
                          for s in data_dict.keys()],
                 value=['RTT'],
                 multi=True
                 ),
    html.Div(children=html.Div(id='graphs'), className='row'),
    dcc.Interval(
        id='graph-update',
        interval=1000),
], className="container", style={'width': '98%', 'margin-left': 10, 'margin-right': 10, 'max-width': 50000})


@app.callback(dash.dependencies.Output('graphs', 'children'),
              [dash.dependencies.Input('latency-name', 'value')],
              events=[dash.dependencies.Event('graph-update', 'interval')])
def update_graph(data_names):
    graphs = []

    lg.times.append(time.time())

    if len(data_names) > 2:
        class_choice = 'col s12 m6 l4'
    elif len(data_names) == 2:
        class_choice = 'col s12 m6 l6'
    else:
        class_choice = 'col s12'

    for data_name in data_names:
        data = go.Scatter(
            x=list(lg.times),
            y=list(data_dict[data_name]),
            name='Scatter',
            fill="tozeroy",
            fillcolor="#6897bb"
        )

        graphs.append(html.Div(dcc.Graph(
            id=data_name,
            animate=True,
            figure={'data': [data], 'layout': go.Layout(xaxis=dict(range=[min(lg.times), max(lg.times)]),
                                                        yaxis=dict(range=[min(data_dict[data_name]) - (min(data_dict[data_name]) / 10),
                                                                          max(data_dict[data_name])
                                                                          + (max(data_dict[data_name]) / 10)]),
                                                        margin={'l': 50, 'r': 1, 't': 45, 'b': 1},
                                                        title='{}'.format(data_name))}
        ), className=class_choice))

    return graphs


external_css = ["https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/css/materialize.min.css"]
for css in external_css:
    app.css.append_css({"external_url": css})

external_js = ['https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/js/materialize.min.js']
for js in external_css:
    app.scripts.append_script({'external_url': js})
