'''
Read in data that is served through TABS website and more.

More information and data locations:
TABS website: http://tabs.gerg.tamu.edu
TWDB data: http://waterdatafortexas.org/coastal
USGS stream gauges in TX: https://txpub.usgs.gov/txwaterdashboard/index.html
'''

import pandas as pd
import re
import traceback


def meta(buoy):
    '''Return metadata for buoy.'''

    # csv file with buoy attributes for TABS website
    loc = 'https://raw.githubusercontent.com/kthyng/tabswebsite/master/includes/buoys.csv'

    bys = pd.read_csv(loc, index_col=0)

    return bys.loc[buoy]  # return all attributes for buoy


def read(buoy, dstart=None, dend=None, tz='UTC', freq='iv', var='flow',
         resample=None, binning='hour', model=False, s_rho=-1, datum=None,
         table=None, waterair=True):
    '''Wrapper so you don't have to know what kind of buoy it is.

    buoy (str): the name of a data station, particularly in Texas, but other
      USGS stream gauges should work, and any time series from TWDB or TABS.
      Add '_full' to a PORTS station to get any available full ADCP profile.
    dstart, dend should be strings that are interpretable by pd.Timestamp. These
      are not required for TWDB data or for full ADCP profiles.
    tz: 'UTC' by default but could also be 'US/Central'
    freq keyword is for USGS data: (default 'iv') 'iv' is instantaneous values, and 'dv' is daily
    var keyword is for USGS data: (default 'flow') 'flow' is m^3, 'height' is m, 'storage' is m^3
    resample will interpolate to upsample or take the average to downsample
      data. If used, input a tuple with the desired period of data, the
      base value, and whether you want an instantaneous approximation or
      an average. The code will figure out if this is down- or up-sampling. If
      it is upsampling, instantaneous is your only reasonable choice.
      For example, `resample=('15T',0,'instant',True)` for resampling to 15 minutes
      starting at 0 minutes on the hour and will interpolate to find the
      instantaneous value between given values.
      `resample=('15T',0,'mean',True)` will take an average of values and only makes
      sense if downsampling.
      The resulting time series will be labeled at the middle of the
      interval that a mean was taken over, if a mean was taken,
      if resample[3]==True, otherwise if resample[3]==False, the label will be
      given at the beginning of the time window.
    binning (default 'hour'): string, only used by TWDB data
    model (False): boolean. If True, read model output for station instead of data.
    s_rho (-1): integer. For model output only. Index of vertical layer of model
      output. -1 is the surface, -999 is for all depths, and the user can choose
      an index between 0 and 29.
    datum (default None): if None, default of MSL is read in. Can be
      'MSL', 'MHHW', 'MHW', 'MLW', 'MLLW', 'MTL' for tidal height. Only used in
      data that has tidal elevation.
    table (default None): This gives the specific TABS buoy table, if you don't
      want all tables combined together. Options are 'ven', 'salt', 'met',
      'wave', and 'eng'. Not all tables are available for all stations. Using
      this option is the only way to get the 'eng' data through this package.
      Using the default of None with a call to a TABS station will get you all
      of the data combined together.
    waterair (default True): If True, add parenthetical to keys with velocity
      or direction units to disambiguate.

    Note that TABS data is by default resampled to 30 minutes since otherwise
      wave data introduces regular nan's. This can be overridden with user-input
      resample choices.

    Example usage:
        import tabs
        df = tabs.read('BOLI')
        df = tabs.read('g06010', '2017-8-1', '2017-8-10')

    Can easily combine dataframes after reading in from different stations with
        df = df.join(tabs.read('EAST'), how='outer')
    '''

    # use pandas Timestamp functionality to interpret input datetimes
    if dstart is not None:
        dstart = pd.Timestamp(dstart)
        dend = pd.Timestamp(dend)
        assert isinstance(dstart, pd.Timestamp) and isinstance(dend, pd.Timestamp), 'dstart and dend should be interpretable by pandas.Timestamp'

    try:
        if model:  # use model output
            assert dstart is not None and dend is not None, 'dstart and dend should be strings with datetimes'
            df = read_other(buoy, dstart, dend, model=True, s_rho=s_rho, datum=datum)
        elif len(buoy) == 1:  # TABS
            assert dstart is not None and dend is not None, 'dstart and dend should be strings with datetimes'
            df = read_tabs(buoy, dstart, dend, table)
            # resample to 30 minutes if not told otherwise and if combining
            # tables together.
            if resample is None and table is None:
                resample = ('30T', 0, 'instant', False)
        elif len(buoy) == 8 or isinstance(buoy, list):  # USGS
            assert dstart is not None and dend is not None, 'dstart and dend should be strings with datetimes'
            df = read_usgs(buoy, dstart, dend, freq, var)
        elif buoy.isalpha():  # TWDB stations are only letters but of varying length
            df = read_twdb(buoy, dstart, dend, binning=binning)
        else:
            if 'full' not in buoy:
                assert dstart is not None and dend is not None, 'dstart and dend should be strings with datetimes'
            df = read_other(buoy, dstart, dend, datum=datum)

        # catch if dataframe is empty
        if df.empty:
            print('Dataframe was empty. Maybe the requested time series is not available for this time period.')
            return None

        # need to change column name if not UTC timezone
        if tz != 'UTC':
            df = df.tz_convert(tz)
            df.index.name = 'Dates [US/Central]'
        else:
            df.index.name = 'Dates [UTC]'

        # add water and air identifiers to those keys to disambiguate
        watercols = ['[cm/s]' in col or 'Dir [deg T]' in col for col in df.columns]
        if watercols.count(True) and waterair:
            for watercol in df.columns[watercols]:
                df.rename(columns={watercol: '%s (water)' % (watercol)}, inplace=True)
        aircols = ['[m/s]' in col or 'Dir from [deg T]' in col for col in df.columns]
        if aircols.count(True) and waterair:
            for aircol in df.columns[aircols]:
                df.rename(columns={aircol: '%s (air)' % (aircol)}, inplace=True)


        if resample is not None:
            # check for upsampling or downsampling
            dt_data = df.index[1] - df.index[0]
            # want start date/time to reflect resample base value
            start = df.index[0].normalize()
            # find time unit from resample input ('min', 'T', 'hour')
            unit = re.split('(\d+)',resample[0])[-1]
            if unit == 'T': unit = 'min'
            if unit == 'H': unit = 'hour'
            deltat = pd.Timedelta(str(resample[1]) + unit)
            start += deltat
            ind = pd.date_range(start, df.index[-1], freq=resample[0], tz=df.index.tz)
            dt_input =  ind[1] - ind[0]
            # allow for resampling over profile data
            if 'Depth to center of bin [m]' in df.columns:
                key = 'Depth to center of bin [m]'
                depths = df[key].unique()
            elif 'Distance to center of bin [m]' in df.columns:
                key = 'Distance to center of bin [m]'
                depths = df[key].unique()
            else:
                depths = None

            if depths is None:
                df = resample_data(df, resample)
            else:
                dfs = []
                for depth in depths:
                    dfs.append(resample_data(df[df[key] == depth], resample))
                df = pd.concat(dfs, axis=0)
                df['colFromIndex'] = df.index  # have to make this column for sorting
                df = df.sort_values(['colFromIndex','Depth to center of bin [m]'], ascending=[True, False])
                df.drop('colFromIndex', axis=1, inplace=True)

        # only output the specified dates and times
        if dstart is not None:
            df = df[dstart:dend]


    except Exception as e:
        print('Exception:\n', e)
        print(traceback.format_exc())
        print('\nNone returned')
        df = None

    return df


def resample_data(df, resample):
    '''Resample data. Up or downsamping.'''

    # check for upsampling or downsampling
    dt_data = df.index[1] - df.index[0]
    start = df.index[0].normalize()
    # find time unit from resample input ('min', 'T', 'hour')
    unit = re.split('(\d+)',resample[0])[-1]
    if unit == 'T': unit = 'min'
    if unit == 'H': unit = 'hour'
    deltat = pd.Timedelta(str(resample[1]) + unit)
    start += deltat
    ind = pd.date_range(start, df.index[-1], freq=resample[0], tz=df.index.tz)
    dt_input =  ind[1] - ind[0]

    # downsampling
    if (dt_data < dt_input) and resample[2] == 'mean':
        if resample[3]:  # shift label for time window to center of window
            loffset = (ind[1] - ind[0])/2
            df = df.resample(resample[0], base=resample[1], label='left', loffset=loffset).mean()
        else:  # keep time label at left end of time window
            df = df.resample(resample[0], base=resample[1]).mean()

    # either upsampling, or downsampling but want instantaneous value
    elif ((dt_data >= dt_input) or ((dt_data < dt_input) and (resample[2] == 'instant'))):
        assert resample[2] == 'instant', 'you did not choose "instant" but it is happening'
        # accounting for known issue for interpolation after sampling if indices changes
        # https://github.com/pandas-dev/pandas/issues/14297
        # interpolate on union of old and new index
        # this step is extraneous if downsampling is a factor of time spacing
        #   but removes nan's ahead of time if not
        df_union = df.reindex(df.index.union(ind)).interpolate(method='time', limit=10)

        # reindex to the new index
        df = df_union.reindex(ind)

    return df


def read_tabs(buoy, dstart, dend, table=None):
    '''Read in data for TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: pandas Timestamp containing start date and time
    dend: pandas Timestamp containing end date and time
    table: see read() docstring
    '''

    tempkey = 'WaterT [deg C]'
    winddirkey = 'Dir from [deg T]'
    windspeedkey = 'Speed [m/s]'
    currentsdirkey = 'Dir [deg T]'
    currentsspeedkey = 'Speed [cm/s]'

    df = pd.DataFrame()
    if table is None:  # combine all tables together
        for table in ['met', 'salt', 'ven', 'wave']:
            url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&table=' + table + '&Datatype=download&units=M&tz=UTC&model=False&datepicker='
            url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
            try:  # not all buoys have all datasets
                dfnew = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999).tz_localize('UTC')

                df = pd.concat([df, dfnew], axis=1)

            # error if instrument doesn't exist; won't include column in df
            except pd.errors.ParserError as e:
                pass

            # error if data not currently available but instrument exists
            # will include columns in df
            except pd.errors.EmptyDataError as e:
                # read columns from daily-created file from website
                url2 = 'http://pong.tamu.edu/tabswebsite/daily/tabs_%s_%s' % (buoy, table)
                columns = pd.read_table(url2, nrows=0).columns
                dfnew = pd.DataFrame(columns=columns)
                # this makes sure that the columns still exist even if data
                # wasn't available
                df = pd.concat([df, dfnew], axis=1)

            except Exception as e:
                print(e)

            # Deal with temperature coming from two instruments
            if tempkey in df.columns:  # df is empty if no data
                if table == 'salt':
                    df.rename(columns={tempkey: '%s (microcat)' % (tempkey)}, inplace=True)
                elif table == 'ven':
                    df.rename(columns={tempkey: '%s (dcs)' % (tempkey)}, inplace=True)

    else:  # just read in one table
        url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&table=' + table + '&Datatype=download&units=M&tz=UTC&model=False&datepicker='
        url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
        try:  # not all buoys have all datasets
            df = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999).tz_localize('UTC')
        except:
            pass


    # change column names to include station name
    if not df.empty:  # df is empty if no data
        df.columns = [buoy + ': ' + col for col in df.columns]

    return df


def read_other(buoy, dstart=None, dend=None, model=False, s_rho=-1, datum=None):
    '''Read in data for non-TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: pandas Timestamp object. Can be None if want full
      velocity data from PORTS stations.
    dend: pandas Timestamp object. Can be None if want full
      velocity data from PORTS stations.
    model (default False): if True, will read in model output instead of data
    datum (default None): if None, default of MSL is read in. Can be
      'MSL', 'MHHW', 'MHW', 'MLW', 'MLLW', 'MTL' for tidal height.
    '''

    if 'full' in buoy:
        url = 'http://pong.tamu.edu/tabswebsite/daily/%s_all' % buoy
        df = pd.read_table(url, na_values=-999, parse_dates=True, index_col=0).tz_localize('UTC')
        if dstart is not None:
            df = df[dstart:dend]

    else:

        url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&Datatype=download&units=M&tz=UTC&datepicker='
        url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
        if model:
            url += '&modelonly=True&model=True&s_rho=' + str(s_rho)
        else:
            url += '&modelonly=False&model=False'
        if datum is not None:
            url += '&datum=' + datum
        df = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999).tz_localize('UTC')
        # change column names to include station name
        df.columns = [buoy + ': ' + col for col in df.columns]

    return df


def read_twdb(buoy, dstart=None, dend=None, binning='hour'):
    '''Read in data from TWDB site.

    if dstart is None, all available data in time will be read in.
    binning (default 'hour') can be: 'mon' (monthly), 'day' (daily), 'hour' (hourly), 'min' (minutes)
    '''

    Files = ['seawater_salinity', 'water_depth_nonvented', 'water_temperature',
             'water_dissolved_oxygen_concentration',
             'water_dissolved_oxygen_percent_saturation', 'water_ph',
             'water_turbidity']
    filenames = ['Salinity', 'Depth [m]', 'WaterT [deg C]',
                 'Dissolved oxygen concentration [mgl]',
                 'Dissolved oxygen saturation concentration [%]', 'pH level',
                 'Turbidity [ntu]']
    base = 'https://waterdatafortexas.org/coastal/api/stations/'
    df = pd.DataFrame()
    for File, filename  in zip(Files, filenames):
        # read in as UTC
        url = base + buoy + '/data/' + File + '?output_format=csv&binning=' + binning
        if dstart is not None:
            url += '&start_date=' + dstart.strftime('%Y-%m-%d') + '&end_date=' + dend.strftime('%Y-%m-%d')
        try:
            dft = pd.read_csv(url, index_col=0,
                             parse_dates=True, comment='#', header=0,
                             names=['Dates [UTC]', filename]).tz_localize('UTC')
            df = pd.concat([df, dft], axis=1)
        except:
            pass

    df.columns = [buoy + ': ' + col for col in df.columns]

    return df


def read_usgs(buoy, dstart, dend, freq='iv', var='flow'):
    '''Uses package hydrofunctions.

    buoy can be a list of strings for USGS
    dstart: pandas Timestamp object.
    dend: pandas Timestamp object.
    freq can be 'iv' (default) for instantaneous flow rate readings or 'dv'
      for daily values.
    var can be 'flow' (default) for stream flow data in m^3/s, 'height' for
      gauge height data in m, or 'storage' for reservoir storage in m^3.
      Not all stations have both.
    '''

    import hydrofunctions as hf

    if var == 'flow':
        code = '00060'
    elif var == 'height':
        code = '00065'
    elif var == 'storage':
        code = '00054'

    df = hf.NWIS(buoy, freq, dstart.strftime('%Y-%m-%d'), dend.strftime('%Y-%m-%d'), parameterCd=code).get_data().df().tz_localize('UTC')
    # drop qualifiers column(s)
    df.drop(df.iloc[:,['qualifiers' in col for col in df.columns]], axis=1, inplace=True)

    if var == 'flow':
        # convert from ft^3/s to m^3/s
        df *= 0.3048**3  # to m^3/s
        # rename
        name = 'Flow rate [m^3/s]'
    elif var == 'height':
        # convert from ft to m
        df *= 0.3048  # to m
        # rename
        name = 'Gage height [m]'
    elif var == 'storage':
        df *= 1233.48  # convert from acre-foot to m^3
        # rename
        name = 'Reservoir storage [m^3]'
    df.columns = [col.split(':')[1] + ': ' + name for col in df.columns]

    return df
