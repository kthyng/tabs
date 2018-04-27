'''
Read in data that is served through TABS website.
'''

import pandas as pd


def read(buoy, dstart, dend, tz='UTC', freq='iv', var='flow', resample=None):
    '''Wrapper so you don't have to know what kind of buoy it is.

    freq keyword is for USGS data: 'iv' is instantaneous values, and 'dv' is daily
    var keyword is for USGS data: 'flow' is m^3 and 'height' is m, 'storage' is m^3
    resample will interpolate to upsample or take the average to downsample
      data. If used, input a tuple with the desired period of data, the
      base value, and whether you want an instantaneous approximation or
      an average. The code will figure out if this is down- or up-sampling. If
      it is upsampling, instantaneous is your only reasonable choice.
      For example, `resample=('15T',0,'instant')`` for resampling to 15 minutes
      starting at 0 minutes on the hour and will interpolate to find the
      instantaneous value between given values.
      `resample=('15T',0,'mean')` will take an average of values and only makes
      sense if downsampling.

    Note that TABS data is by default resampled to 30 minutes since otherwise
      wave data introduces regular nan's.
    '''

    # use pandas Timestamp functionality to interpret input datetimes
    dstart = pd.Timestamp(dstart)
    dend = pd.Timestamp(dend)

    if len(buoy) == 1:  # TABS
        df = read_tabs(buoy, dstart, dend, tz)
        if resample is None:  # resample to 30 minutes if not told otherwise
            resample = ('30T', 0, 'instant')
    elif len(buoy) == 8 or isinstance(buoy, list):  # USGS
        df = read_usgs(buoy, dstart, dend, freq, var, tz)
    elif len(buoy) == 4:  # TWDB
        df = read_twdb(buoy, dstart, dend, tz)
    else:
        df = read_other(buoy, dstart, dend, tz)

    if resample is not None:

        # check for upsampling or downsampling
        dt_data = df.index[1] - df.index[0]
        ind = pd.date_range(dstart, dend, freq=resample[0], tz=tz)
        dt_input =  ind[1] - ind[0]

        # downsampling
        if (dt_data > dt_input) and (resample[2] == 'mean'):

            df = df.resample(resample[0], base=resample[1]).mean()

        # either upsampling or downsampling but want instantaneous value
        elif (dt_data <= dt_input) or \
                ((dt_data > dt_input) and (resample[2] == 'instant')):


            # accounting for known issue for interpolation after sampling if indices changes
            # https://github.com/pandas-dev/pandas/issues/14297
            # interpolate on union of old and new index
            # this step is extraneous if downsampling is a factor of time spacing
            #   but removes nan's ahead of time if not
            df_union = df.reindex(df.index.union(ind)).interpolate(method='time', limit=2)

            # reindex to the new index
            df = df_union.reindex(ind)

    return df



def read_tabs(buoy, dstart, dend, tz='UTC'):
    '''Read in data for TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: string containing start date and time
    dend: string containing end date and time
    tz: 'UTC' by default but could also be 'US/Central'

    Note that data are resampled to be every 30 minutes to have a single dataframe.
    '''

    df = pd.DataFrame()
    for table in ['met', 'salt', 'ven', 'wave']:
        url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&table=' + table + '&Datatype=download&units=M&tz=' + tz + '&model=False&datepicker='
        url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
        try:  # not all buoys have all datasets
            dfnew = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999)[dstart:dend].tz_localize(tz)
            df = pd.concat([df, dfnew], axis=1)
        except:
            pass

    # change column names to include station name
    df.columns = [buoy + ': ' + col for col in df.columns]

    return df


def read_other(buoy, dstart, dend, tz='UTC'):
    '''Read in data for non-TABS buoy. Return dataframe.

    buoy: string containing buoy name
    dstart: string containing start date and time
    dend: string containing end date and time
    tz: 'UTC' by default but could also be 'US/Central'

    Note that data are resampled to be every 30 minutes to have a single dataframe.
    '''

    url = 'http://pong.tamu.edu/tabswebsite/subpages/tabsquery.php?Buoyname=' + buoy + '&Datatype=download&units=M&tz=' + tz + '&model=False&datepicker='
    url += dstart.strftime('%Y-%m-%d') + '+-+' + dend.strftime('%Y-%m-%d')
    try:
        df = pd.read_table(url, parse_dates=True, index_col=0, na_values=-999)[dstart:dend].tz_localize(tz)

        # change column names to include station name
        df.columns = [buoy + ': ' + col for col in df.columns]
    except:
        print('Data not available')

    return df


def read_twdb(buoy, dstart, dend, tz='UTC'):
    '''Read in data from TWDB site.'''

    Files = ['seawater_salinity', 'water_depth_nonvented', 'water_temperature']
    filenames = ['Salinity', 'Depth [m]', 'WaterT [deg C]']
    base = 'https://waterdatafortexas.org/coastal/api/stations/'
    df = pd.DataFrame()
    for File, filename  in zip(Files, filenames):
        # read in as UTC
        url = base + buoy + '/data/' + File + '?output_format=csv&binning=hour'
        dft = pd.read_csv(url, index_col=0,
                         parse_dates=True, comment='#', header=0,
                         names=['Dates [UTC]', filename])[dstart:dend].tz_localize('UTC')
        df = pd.concat([df, dft], axis=1)

    # change column names to include station name
    df.columns = [buoy + ': ' + col for col in df.columns]

    # need to change column name if not UTC timezone
    if tz != 'UTC':
        df = df.tz_convert(tz)
        df.index.name = 'Dates [US/Central]'

    return df


def read_usgs(buoy, dstart, dend, freq='iv', var='flow', tz='UTC'):
    '''Uses package hydrofunctions.

    buoy can be a list of strings for USGS
    freq can be 'iv' (default) for instantaneous flow rate readings or 'dv'
      for daily values.
    var can be 'flow' (default) for stream flow data in m^3/s, 'height' for
      gauge height data in m, or 'storage' for reservoir storage in m^3.
      Not all stations have both.

    Can pip install hydrofunctions.
    '''

    import hydrofunctions as hf

    if var == 'flow':
        code = '00060'
    elif var == 'height':
        code = '00065'
    elif var == 'storage':
        code = '00054'

    df = hf.NWIS(buoy, freq, dstart.strftime('%Y-%m-%d'), dend.strftime('%Y-%m-%d'), parameterCd=code).get_data().df()[dstart:dend].tz_localize('UTC').tz_convert(tz)
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
    # need to change column name if not UTC timezone
    if tz != 'UTC':
        df = df.tz_convert(tz)
        df.index.name = 'Dates [US/Central]'
    else:
        df.index.name = 'Dates [UTC]'

    return df
