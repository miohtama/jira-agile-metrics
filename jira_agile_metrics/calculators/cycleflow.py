import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from ..calculator import Calculator
from ..utils import get_extension, set_chart_style

from .cycletime import CycleTimeCalculator

logger = logging.getLogger(__name__)


class CycleFlowCalculator(Calculator):
    """Create the data to build a non-cumulate flow diagram: a DataFrame,
    indexed by day, with columns containing cumulative days for each
    of the items in the configured cycle.

    """

    def run(self):

        cycle_data = self.get_result(CycleTimeCalculator)

        # Exclude backlog and done
        active_cycles = self.settings["cycle"][1:-1]

        cycle_names = [s['name'] for s in active_cycles]

        return calculate_cycle_flow_data(cycle_data, cycle_names)

    def write(self):
        data = self.get_result()

        if self.settings['cycle_flow_chart']:
            if data:
                self.write_chart(data, self.settings['cycle_flow_chart'])
            else:
                logger.info("Did not match any entries for cycle flow chart")
        else:
            logger.debug("No output file specified for cycle flow chart")

    def write_chart(self, data, output_file):

        if len(data.index) == 0:
            logger.warning("Cannot draw cycle flow without data")
            return

        fig, ax = plt.subplots()

        ax.set_title("Cycle flow")
        data.plot.area(ax=ax, stacked=True, legend=False)
        ax.set_xlabel("Period of issue complete")
        ax.set_ylabel("Time spent (days)")

        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

        set_chart_style()

        # Write file
        logger.info("Writing cycle flow chart to %s", output_file)
        fig.savefig(output_file, bbox_inches='tight', dpi=300)
        plt.close(fig)


def calculate_cycle_flow_data(cycle_data, cycle_names, frequency="1M", resample_on="completed_timestamp"):
    """Calculate diagram data for times spent in different cycles.

    :param cycle_data: Cycle time calculator outpu

    :param cycle_names: List of cycles includedin the flow chat

    :param frequency: Weekly, monthly, etc.

    :param resample_on: Column that is used as the base for frequency - you can switch between start and completed timestamps
    """

    # Build a dataframe of just the "duration" columns
    duration_cols = [f"{cycle} duration" for cycle in cycle_names]
    cfd_data = cycle_data[[resample_on] + duration_cols]

    # Zero out missing data, e.g. for tickets that were created and closed immediately
    cfd_data = cfd_data.fillna(pd.Timedelta(seconds=0))

    # Remove issues that lack completion date
    # https://stackoverflow.com/a/55066805/315168
    cfd_data = cfd_data[cfd_data[resample_on] != pd.Timedelta(seconds=0)]

    # We did not have any issues with completed_timestamp,
    # cannot do resample
    if cfd_data.empty:
        return None

    sampled = cfd_data.resample(frequency, on=resample_on).agg(np.sum)

    #
    # Sample output
    #                         Development duration          Fixes duration         Review duration             QA duration
    # completed_timestamp
    # 2020-02-29           0 days 00:02:14.829000  0 days 01:21:01.586000  0 days 06:21:59.009000  1 days 13:19:26.173000
    # 2020-03-31           4 days 04:53:44.114000  0 days 19:13:43.590000  1 days 00:51:11.272000  2 days 01:54:57.958000
    # 2020-04-30           6 days 11:48:55.864000  1 days 15:48:23.789000  3 days 17:51:01.561000 10 days 11:54:59.661000

    # Convert Panda Timedeltas to days as float
    # sampled = sampled[duration_cols].apply(lambda x: float(x.item().days))
    # https://stackoverflow.com/a/54535619/315168
    sampled[duration_cols] = sampled[duration_cols] / np.timedelta64(1, 'D')

    # Fill missing values with zero duration
    sampled = sampled.fillna(0)

    # Make sure we always return stacked charts in the same order
    # TODO: Not 100% sure if this is needed
    sampled.columns = pd.CategoricalIndex(sampled.columns.values,
                                    ordered=True,
                                    categories=duration_cols)


    # Sort the columns (axis=1) by the new categorical ordering
    sampled = sampled.sort_index(axis=1)

    return sampled
