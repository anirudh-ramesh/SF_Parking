#!/usr/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import datetime as dt
import time
from scipy import stats
import geopandas as gpd
import sqlite3
import math
from shapely.geometry import Point
from geopandas import GeoSeries, GeoDataFrame
import mplleaflet
from IPython.display import HTML
from matplotlib.animation import FuncAnimation

global conn

raw_loc= '/home/colin/Desktop/SF_Parking/data/raw/'
proc_loc = '/home/colin/Desktop/SF_Parking/data/processed/'

conn = sqlite3.connect(proc_loc + 'SF_Parking.db')


def load_files():
    """Loads all required dataframes for use.
    Returns
    -------
    dataframes
        address data, streetvolume(geo), nhoods(geo), streetsweeping(geo)

    """
    address_data = pd.read_sql_query('Select * from address_data', conn)
    streetvolume = gpd.read_file(proc_loc + './final_streets/SF_Street_Data.shp')
    nhoods = gpd.read_file(raw_loc + 'AnalysisNeighborhoods.geojson')
    streetsweeping = gpd.read_file(proc_loc + 'final_sweeping.shp')
    return address_data, streetvolume, nhoods, streetsweeping

def create_routes():
    """Queries sql for our last ticket of every day for each street link, returns into dataframe.

    Returns
    -------
    dataframe
        dataframe detailing route and ticket times.

    """
    by_route = result_query("Select  strftime('%Y-%m-%d', TickIssueDate) as sweepdate, lineid, "
                        " max(strftime('%H:%M',TickIssueDate)) as last_ticket from ticket_data t1 "
                       " join address_data t2 on t1.address = t2.address WHERE ViolationDesc = 'STR CLEAN' "
                    " group by strftime('%Y-%m-%d', TickIssueDate) ,  lineid")
    by_route['weekday'] = by_route['sweepdate'].apply(lambda x: pd.to_datetime(x).weekday())
    by_route['mins'] = by_route['last_ticket'].apply(lambda x: int(x.split(':')[0]) * 60 + int(x.split(':')[1]))
    return by_route


def live_day_graph(datestring, folderloc, address_data):
    """This function will take the date as an argument, and then it will create a live graph of a day, plotting tickets as they were given out that day.

    Parameters
    ----------
    datestring : string
        date, in form of string. that is the date you would like to query. Must be in format %d-%m-%Y.
    folderloc: string
        stirng of folder location where to save file

    Returns
    -------
    type
        Description of returned object.

    """

    fig = plt.figure(figsize = (20,20))
    plt.rcParams["animation.html"] = "jshtml"
    plt.rcParams["animation.embed_limit"] = 100
    ax = plt.axes()
    df = pd.read_sql_query("Select * from ticket_data where strftime('%d-%m-%Y', TickIssueDate) = '" + datestring + "'")
    df = df.merge(address_data, left_on = 'address', right_on = 'address')
    df['color'] = df['ViolationDesc'].apply(lambda x: colordict.get(x, 'magenta'))
    ax.set_title('Parking tickets on XXX')
    geometry = [Point(xy) for xy in zip(df.lon, df.lat)]
    crs = {'init': 'epsg:4326'}
    gdf = GeoDataFrame(df, crs=crs, geometry=geometry)
    nhoods = gpd.read_file(raw_folder + 'AnalysisNeighborhoods.geojson')



    nhoods.plot( ax = ax, alpha = .15, color = 'gray')
    # First set up the figure, the axis, and the plot element we want to animate
    streetvolume.plot(ax =ax, color = 'black', figsize = (20, 20), alpha =.25, linewidth = 1)
    gdf.sort_values(by = 'TickIssueDate', inplace = True)
    gdf['TickIssueDate'] = gdf['TickIssueDate'].apply(lambda x: dt.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
    gdf['TickIssueTime'] = gdf['TickIssueDate'].apply(lambda x: x.time().hour*4 + int(x.time().minute / 15))
    gdf.set_index('TickIssueTime', inplace = True)
    ttl = ax.text(.5, 1.05, '', transform = ax.transAxes, va='center')
    numframes = gdf.shape[0]
    i = 0

    def animate(i):
        df = gdf[i-1:i]
        timestr = (str(math.floor(i/4)) + ':' + str((i %4) * 15))
        colors = df['color']
        iterar = df.plot(ax = ax, marker = '*', c = colors, markersize = 10 )
        ttl.set_text(timestr)
        i += 1
        return iterar

    ani = FuncAnimation(fig, animate, repeat=False, interval=94)
    #plt.show()
    ani.save(datestring, folderloc)


def getweekofmon(dt):
    """function to take datetime and return what day of week it is.

    Parameters
    ----------
    dt : datetime
        current datetime

    Returns
    -------
    integer
        day of week 0-mon to 7-sun

    """
    first_day = dt.replace(day=1)

    dom = dt.day
    adjusted_dom = dom + first_day.weekday()

    return int(ceil(adjusted_dom/7.0))





def find_recent_street_cleaning(streetnumber, streetname, address_data, ResOT, invalid_ids):
    """Function to find recently cleaned streets. Process will be to first look up closest address, then filter on streets that were cleaned that day.

    Parameters
    ----------
    streetnumber : type
        Description of parameter `streetnumber`.
    streetname : type
        Description of parameter `streetname`.
    ResOT : type
        Description of parameter `ResOT`.

    Returns
    -------
    matplotlib axis


    """
    ad = address_data[address_data.street == streetname]
    if ad.shape[0] == 0:
        return print('Could not find streetname')
    ad['delta'] = np.abs(ad['number'] - streetnumber)
    ad.sort_values(by = 'delta', inplace = True)
    ad = ad.iloc[0]
    df = streetsweeping
    point = Point(ad.lon, ad.lat)

        df = df[df.lineid.isin(invalid_ids['lineid']) == False]

    weekdaydict = {0: 'Mon', 1:'Tues', 2:'Wed', 3:'Thu', 4:'Fri', 5:'Sat', 6:'Sun'}
    time =  dt.datetime.now()

    colname = 'week' + str(week_of_month(time)) + 'ofmon'
    cleaned_today = df[(df.weekday == weekdaydict[time.weekday()]) & (df[colname] == 1)]
    not_today = df[(df.weekday != weekdaydict[time.weekday()]) | (df[colname] == 0)]
    nhoods = gpd.read_file(raw_folder + '/AnalysisNeighborhoods.geojson')
    cleaned_today['distance'] = cleaned_today['geometry'].apply(lambda x: point.distance(x))
    cleaned_today.sort_values(by = 'distance', inplace = True)
    cleaned_today_closest = cleaned_today[:25]



    ax = not_today.plot(color = 'red', alpha = .15)
    ax = cleaned_today.plot( color = 'yellow', alpha = .75)
    cleaned_today[:500].plot(ax = ax, color = 'green', alpha = 1)
    circleaddress = matplotlib.patches.Circle((ad['lon'], ad['lat']), radius = 5)
    mplleaflet.show(fig=ax.figure, crs=cleaned_today.crs)
    plt.show()
    return



def mean_confidence_interval(data, confidence=0.95):
    """Short summary.

    Parameters
    ----------
    data : numpy array
        array of times, minute form
    confidence : float
        confidence interval

    Returns
    -------
    average, lower and uppper confidence interval on what time that street get's cleaned.

    """
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return m, m-h, m+h


def min_to_time(mins):
    """turns minutes into a  %H:%M format

    Parameters
    ----------
    mins : float
        minutes, total number

    Returns
    -------
    string representation of time

    """
    return str(math.ceil(mins / 60)) + ":" + str(int(mins%60))




def return_conf_interval(number, street, by_route, address_data):
    """function looks up the closest address to the input,

    Parameters
    ----------
    number : type
        Description of parameter `number`.
    street : type
        Description of parameter `street`.
    by_route : type
        Description of parameter `by_route`.

    Returns
    -------
    type
        Description of returned object.

    """
    ad = address_data[address_data.street == street]
    if ad.shape[0] == 0:
        return print('Could not find streetname')
    ad['delta'] = np.abs(ad['number'] - number)
    ad.sort_values(by = 'delta', inplace = True)
    streeline = ad['lineid'].iloc[0]
    street_data = by_route[by_route.lineid == streeline]
    if street_data.shape[0] == 0:
        return print('No street sweeping ticket data found for closest address. ')
    mean, low, high = mean_confidence_interval(street_data['mins'])
    print("low: " + min_to_time(low))
    print("mean: " + min_to_time(mean))
    print("High: " + min_to_time(high))



def map_the_route(weekday, by_route, streetvolume):
    """Function to take a weekday and map out from earliest to last where the street sweepers travel.

    Parameters
    ----------
    weekday : string
        string of weekday

    Returns
    -------
    matplotlib chart.

    """

    by_street = by_route[by_route.weekday ==weekday].groupby(by = 'lineid', as_index = False)['mins'].mean()
    df = streetvolume.merge(by_street, left_on = 'lineid', right_on = 'lineid')
    df.plot(cmap = 'RdYlGn', column = 'mins', figsize = (20,20))



def main():
    """Main function to choose which extra you would like to do.

    Returns
    -------
    none

    """
    weekdaydict = {'Mon':1,'Tues':2, 'Wed':3, 'Thurs': 4, 'Fri': 5, 'Sat:'6, 'Sun:' 7)}
    print("Preparing all neccesary datasets")
    address_data, streetvolume, nhoods, streetsweeping = load_data()
    by_route = create_route()
    invalid_ids =pd.read_sql_query('Select distinct lineid from address_data t1 join ticket_data t2 on '
                              " t1.address = t2.address where ViolationDesc = 'RES/OT' ", conn)

    runagain = 'Y'
    while runagan == 'Y'
        choice = input('Which extra would you like to do? 1.Day animation 2.Recent Street Cleaning 3.Estimated Sweeping Time 4. Map the Route ')

        switch(choice) {
        case 1: datestring = input('Which date would you like to make?(format %d-%m-%Y)')
        folderloc = input('What folder would you like to save it?')
        live_day_graph(datestring, folderloc, addresses):
        break;

        case 2: number = input('Whats the number of the address?')
        street = input('What is the full street (name + suffix)')
        resOT = input('Would you like to avoid residential overtime?(Y or N)')
        if resOT = 'Y':
            resOT = True
        else:
            resOT = False
        find_recent_street_cleaning(streetnumber, streetname, address_data, ResOT, invalid_ids):

        case 3: number = input('Whats the number of the address?')
        street = input('What is the full street (name + suffix)')
        return_conf_interval(number, street, by_route, address_data):

        case 4: weekday = input('What day of week would you like to look at?(Mon,Tues, Wed, Thurs, Fri, Sat, Sun)'))
        weekday = weekdaydict(weekday)
        map_the_route(weekday, by_route, streetvolume):

        default runagain = input('Your entry was invalid, would you like to try again ?(Y or N)')
        }

        runagain = input('Would you like to do another?')





if __name__== '__main__':
    main()
