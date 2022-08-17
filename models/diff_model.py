from doltpy.cli.read import read_table_sql
from PyQt5 import QtCore, QtGui

import pandas as pd
import pandasql as ps


# NOTE: https://www.dolthub.com/blog/2022-03-25-dolt-diff-magic/


CHUNKSIZE = 10000


# Overrides doltcli.utils.parse_to_pandas since it converts strings to ints
def parse_to_pandas(sql_output):
    # FIXME: Rather than str for all, get table schema and map based on that.
    # Default to str for all, and only map other convertible types (int, double, etc.)
    return pd.read_csv(sql_output, dtype=str)


# FIXME: Speed up further
def get_diff_chunks(repo, table, commit, filter_query=None):
    query = f"""
    SELECT * FROM dolt_diff_{table} WHERE
        from_commit="{commit.parents}" AND to_commit="{commit.ref}"
        LIMIT {CHUNKSIZE};
    """
    df = read_table_sql(repo, query, result_parser=parse_to_pandas)

    # Remove commit info columns
    df = df.drop(df.filter(regex='^(from|to)_commit(_date)*$').columns, axis=1)

    # Get table PKs
    table_columns = read_table_sql(
        repo, f'DESC {table};', result_parser=parse_to_pandas
    )
    table_pks = list(table_columns[table_columns['Key'] == 'PRI']['Field'])

    # FIXME: DESC doesn't return columns in correct order via DoltCLI - not sure why.
    ordered_columns = list(
        read_table_sql(repo, f'''
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE
            table_name="{table}" ORDER BY ordinal_position;
        ''', result_parser=parse_to_pandas)['COLUMN_NAME']
    )

    # Combine from/to columns into one
    columns = [
        (col, f"from_{col}", f"to_{col}")
        for col in df.columns.str.extract('^to_(.*)', expand=False).dropna()
    ]
    for col, from_col, to_col in columns:
        df[col] = df[to_col]
        df.loc[df['diff_type'] == 'removed', col] = df[from_col]

    # Sort on to_<pk> for all PKs
    df = df.sort_values(table_pks)

    # Apply filter
    if filter_query:
        df = ps.sqldf(filter_query)

    # Modified overlay - each cell will be a list with values: [before, after]
    # NOTE: This is done after sorting as it fails on list items
    modified = df['diff_type'] == 'modified'
    for merged_col, from_col, to_col in columns:
        # Convert individually to lists, then add them to concatenate
        from_ = df[from_col].apply(lambda obj: list([obj]))
        to = df[to_col].apply(lambda obj: list([obj]))
        df.loc[modified, merged_col] = from_ + to

    # Insert modified_to rows directly below original modified row
    # https://stackoverflow.com/questions/45565311/pandas-interleave-zip-two-dataframes-by-row#comment80868881_45565489
    df.loc[modified, 'diff_type'] = 'modified_from'
    df = df.append(
        df.loc[modified].assign(diff_type='modified_to')
    ).sort_index(kind='mergesort', ignore_index=True)

    # diff_symbols (+ or - depending on diff_type)
    diff_symbols = df['diff_type'].apply(
        lambda diff_type: '+' if diff_type in ['added', 'modified_to'] else '−'
    )

    # Drop from/to columns and reorder so diff_type is at the end
    df = df[ordered_columns + ['diff_type']]
    df.insert(0, '', diff_symbols)

    return df


class DiffModel(QtCore.QAbstractTableModel):
    diff = {}
    current_table = None

    def __init__(self, repo, table_list, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.table_list = table_list

        self.font = QtGui.QFont("Courier New")
        self.font.setStyleHint(QtGui.QFont.Monospace)

    def load_diff(self, repo, commit):
        query = f'SELECT DISTINCT table_name FROM dolt_diff WHERE commit_hash="{commit.ref}";'
        tables = read_table_sql(repo, query)

        # Read first 10k - then only load when scrolling halfway / near end of chunk
        self.diff = {
            table["table_name"]: get_diff_chunks(repo, table["table_name"], commit)
            for table in tables
        }

        self.current_table = list(self.diff)[0]

        self.table_list.clear()
        self.table_list.addItems(list(self.diff))
        self.table_list.setCurrentRow(0)

    def data(self, index, role):
        row = self.diff[self.current_table].iloc[index.row()]
        value = row.iloc[index.column()]

        if row['diff_type'].startswith('modified') and index.column() != 0:
            mod = value[0] != value[1]  # Unmodified if both values in column are same
            value = value[0 if row['diff_type'] == 'modified_from' else 1]

        if role == QtCore.Qt.FontRole:
            return self.font
        elif role == QtCore.Qt.DisplayRole:
            if pd.isna(value):
                return 'NaN'
            return str(value)
        elif role == QtCore.Qt.ForegroundRole:
            if pd.isna(value):
                return QtGui.QColor(149, 163, 167, 125)
            elif row['diff_type'] == 'added':
                return QtGui.QColor('#5AC58D')
            elif row['diff_type'] == 'removed':
                return QtGui.QColor('#FF9A99')
            elif row['diff_type'] == 'modified_from' and (index.column() == 0 or mod):
                return QtGui.QColor('#FF9A99')
            elif row['diff_type'] == 'modified_to' and (index.column() == 0 or mod):
                return QtGui.QColor('#5AC58D')
            else:
                return QtGui.QColor('#95A3A7')
        elif role == QtCore.Qt.BackgroundRole:
            if row['diff_type'] == 'added':
                return QtGui.QColor('#DDFAE3')
            elif row['diff_type'] == 'removed':
                return QtGui.QColor('#FEE9EB')
        elif role == QtCore.Qt.TextAlignmentRole:
            return int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return self.diff[self.current_table].columns[section]
            elif role == QtCore.Qt.TextAlignmentRole:
                return int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

    def rowCount(self, index):
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table])

    def columnCount(self, index):
        if not self.current_table:
            return 0
        return len(self.diff[self.current_table].columns)-1  # -1 to exclude diff_type

    def filter_query(self, repo, commit, query):
        self.beginResetModel()
        self.diff[self.current_table] = get_diff_chunks(
            repo, self.current_table, commit, query
        )
        self.endResetModel()

    def get_longest_str(self, col_no):
        # Explode to split rows with modified overlay
        column = self.diff[self.current_table].iloc[:, col_no]
        column = column.append(pd.Series(column.name))  # Default size
        column = column.explode().reset_index(drop=True).astype(str)

        lengths = column.str.len()
        return column[lengths[lengths == lengths.max()].index[0]]
