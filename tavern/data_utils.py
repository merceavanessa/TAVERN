import numpy as np


def set_activity_level(df, geomagnetic_storm_levels):
    df['activity_level'] = df['Kp'].apply(lambda kp: next((level for level, (low, high) in geomagnetic_storm_levels.items() if low <= kp <= high), 'Unknown'))

    #  propagate backward the strongest activity levels until the transition to quiet level to the left and right e.g. G1 G3 G2 G5 G1 -> G1 strong G5 G5 G5 G1
    activity = df['activity_level'].values
    for level in ["G5 (Extreme)", "G4 (Severe)", "G3 (Strong)", "G2 (Moderate)", "G1 (Minor)"]:
        is_not_quiet = activity != 'G0 (Quiet to Unsettled)'
        is_level = activity == level
        regions = np.flatnonzero(np.diff(np.concatenate(([0], is_not_quiet.view(np.int8), [0]))))
        for start, end in zip(regions[::2], regions[1::2]):
            if is_level[start:end].any():
                activity[start:end] = level
    df['activity_level'] = activity

    # if less than N points of one activity level between two stronger activity levels, propagate the stronger activity level to those points
    N = 3 * 60 * 3 # 3 hours
    activity = df['activity_level'].values
    regions = np.flatnonzero(np.diff(np.concatenate(([0], activity != activity[0],
        [0]))))
    for start, end in zip(regions[::2], regions[1::2]):
        if end - start < N:
            left_level = activity[start - 1] if start > 0 else None
            right_level = activity[end] if end < len(activity) else None
            if left_level == right_level and left_level is not None and left_level != 'G0 (Quiet to Unsettled)':
                activity[start:end] = left_level
    df['activity_level'] = activity

    df = annotate_geomagnetic_storm_events(df, geomagnetic_storm_levels)
    df['decay_level'] = df['aDot_m_s'].rank(pct=True)
    return df

def annotate_geomagnetic_storm_events(df, geomagnetic_storm_levels):
    for i, level in enumerate(geomagnetic_storm_levels.keys()):
        if 'G0' in level:
            continue

        activity = df['activity_level'].values
        is_level = activity == level
        regions = np.flatnonzero(np.diff(np.concatenate(([0], is_level.view(np.int8), [0]))))
        event_count = len(regions) // 2
        data_samples_per_region = [regions[i + 1] - regions[i] for i in range(0, len(regions), 2)]
        df.loc[df['activity_level'] == level, 'event_number'] = np.repeat(np.arange(1, event_count + 1),
                                                                          data_samples_per_region)
        df.loc[df['activity_level'] == level, 'unique_event_id'] = [int(f'{i}{n}') for n in
                                                                    np.repeat(np.arange(1, event_count + 1),
                                                                              data_samples_per_region)]

    return df