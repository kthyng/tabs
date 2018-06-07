# tabs
For easily reading in data and model time series from [TABS website](http://pong.tamu.edu/tabswebsite).

To install:
1. Clone the repository somewhere you store packages on your computer:
> git clone https://github.com/kthyng/tabs.git
2. Change directories into this new directory:
> cd tabs
3. Locally install the package
> pip install --user -e .

You should now be able to `import tabs` from any Python script, ipython window, or Jupyter notebook.

## Notes:

The basic call is

`tabs.read(BUOYNAME, DATETIME START STRING, DATETIME END STRING)`

and returns a `pandas` dataframe. Missing values are filled in with `np.nan`. If data is not available, `None` is returned and exception is printed. Column names describe data and units and are prepended with station name followed by a colon.

The date/time strings have to be interpretable by [`pandas Timestamp`](https://pandas.pydata.org/pandas-docs/stable/generated/pandas.Timestamp.html) function.

Available data stations are:
* Any station listed on the TABS website: http://pong.tamu.edu/tabswebsite.
* Texas Water Development Board coastal time series data: http://waterdatafortexas.org/coastal
* Any USGS stream gauges. A nice website is available that shows the Texas stations: https://txpub.usgs.gov/txwaterdashboard/index.html
* Model output from a [ROMS model of the Texas and Louisiana continental shelves](http://pong.tamu.edu/tabswebsite/subpages/models.php) and from NOAA is available at many of the stations listed on the TABS website, as visible on the buoy listing on the front page.

## Example Usage:

1. Read in all available types of data (which will include all of or a subset of: currents, temperature, salinity, winds, air temperature, and wave data) for a TABS buoy over a given time range. Data is resampled to every half hour by default since different instruments are available at different rates. This can be overridden with user-input resample choices.

> df = tabs.read('B', '2018-1-1', '2018-1-10')

2. Read in PORTS data (currents) from Texas and Louisiana area. Can include time if desired:

> df = tabs.read('g06010', '2017-7-1', '2017-7-10 12:00')

3. Read in full ADCP data for PORTS stations, which is either with depth or cross-channel. This data has a matching time stamp for each depth or cross-channel bin.

> df = tabs.read('g06010_full', '2017-7-1', '2017-7-10')

4. A specific depth (in this example -4.31 m) or cross-channel bin can subsequently selected from a full ADCP profile with the following, with the column name 'Depth to center of bin [m]' for ADCP data with depth or 'Distance to center of bin [m]' for ADCP data across a channel:

> df[df['Depth to center of bin [m]'] == -4.31]

5. Read in NDBC data (usually met data, some wave data is available) from the area:

> df = tabs.read('42001', '2018-5-25 4:00', '2018-6-7 12:00')

6. Read in data from a TCOON buoy (typically sea surface height, met data, water temperature). For any buoy with sea surface height data near the coast, you can select a different vertical datum from the default of Mean Sea Level:

> df = tabs.read('8771972', '2017-1-1', '2017-1-10', datum='MLW')

7. Read in other NOS buoy (similar to TCOON buoys):

> df = tabs.read('8770570', '2017-1-1', '2017-1-10')

8. Read in [Texas Water Development Board](http://waterdatafortexas.org/coastal) time series data. All available data from salinity, temperature, depth, turbidity, Ph, and dissolved oxygen concentration will be read in. If `dstart` is None, all available data will be read in. If given, the file will be subsetted before being returned. Binning of data can be 'mon' (monthly), 'day' (daily), 'hour' (hourly), 'min' (minutes); default 'hour'. If selected `binning` is not available for all datatypes for station, they will not be returned.

> df = tabs.read('BOLI')

9. Read in data from a USGS station, or a list of stations. Input `freq` can be 'iv' (default) for instantaneous flow rate readings or 'dv' for daily values. Daily values are not available for all variables and stations. Input `var` can be 'flow' (default) for stream flow data in m^3/s, 'height' for gauge height data in m, or 'storage' for reservoir storage in m^3. Not all stations have all variables.

> df = tabs.read('08042558', '2018-6-1', '2018-6-7', var='height')

> df = tabs.read(['08042558','08116650'], '2017-1-1', '2017-1-10', var='height')

10. Read in time series output from numerical model of Texas-Louisiana shelf at a station available on the TABS website:

> df = tabs.read('B', '2018-6-2', '2018-6-10', model=True)

11. Read in time series output available from a NOAA model for coastal tidal stations, for either sea surface height or tidal currents at some PORTS stations. This is available for 2 years before and after present day:

> df = tabs.read('8771972', '2018-6-2', '2018-6-10', model=True)

12. After reading in different data, can combine dataframes:

> df = tabs.read('BOLI')

> df = df.join(tabs.read('EAST'), how='outer')

13. We can also combine different sources of data. The result will have nan's at all times that are distinct for the two datasets, which may be most of the times. You can use a `resample` option to fill in the data.

> df = tabs.read('BOLI', '2017-1-1', '2017-1-12')

> df = df.join(tabs.read('8771341', '2017-1-1', '2017-1-10'), how='outer')


14. You can choose to have the data resampled with the keyword argument `resample`. `resample` will interpolate to upsample or take the average to downsample data. If used, input a tuple with the desired [frequency of data](https://pandas.pydata.org/pandas-docs/stable/timeseries.html#timeseries-offset-aliases), the base value, and whether you want an instantaneous approximation or an average. The code will figure out if this is down- or up-sampling. If it is upsampling, instantaneous is your only reasonable choice. For example, `resample=('15T',0,'instant')` for resampling to 15 minutes starting at 0 minutes on the hour and will interpolate to find the instantaneous value between given values. `resample=('15T',0,'mean')` will take an average of values and only makes sense if downsampling. The resulting time series will be labeled at the middle of the interval that a mean was taken over, if a mean was taken.

> df = tabs.read('g06010', '2012-3-1', '2012-3-10', resample=('15T', 0, 'mean'))

15. The default time zone is UTC, but you can instead choose 'US/Central' with the `tz` keyword argument as follows:

> df = tabs.read('F', '2010-5-23', '2010-5-30', tz='US/Central')
