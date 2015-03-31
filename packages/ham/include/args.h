#ifndef HAM_ARGS_H
#define HAM_ARGS_H
#include <map>
#include <set>
#include <fstream>
#include <cassert>

#include <text.h>
#include "tclap/CmdLine.h"
using namespace TCLAP;
using namespace std;
namespace ham {
// ----------------------------------------------------------------------------------------
// input processing class
// NOTE some input is passed on the command line (global configuration), while some is passed in a csv file (stuff that depends on each (pair of) sequence(s)).
class Args {
public:
  Args(int argc, const char * argv[]);
  string hmmdir() { return hmmdir_arg_.getValue(); }
  string datadir() { return datadir_arg_.getValue(); }
  string infile() { return infile_arg_.getValue(); }
  string outfile() { return outfile_arg_.getValue(); }
  string cachefile() { return cachefile_arg_.getValue(); }
  float hamming_fraction_cutoff() { return hamming_fraction_cutoff_arg_.getValue(); }
  string algorithm() { return algorithm_arg_.getValue(); }
  // string algorithm() { return algorithm_; }
  int debug() { return debug_arg_.getValue(); }
  // int debug() { return debug_; }
  int n_best_events() { return n_best_events_arg_.getValue(); }
  bool chunk_cache() { return chunk_cache_arg_.getValue(); }
  bool partition() { return partition_arg_.getValue(); }

  // command line arguments
  vector<string> algo_strings_;
  vector<int> debug_ints_;
  ValuesConstraint<string> algo_vals_;
  ValuesConstraint<int> debug_vals_;
  ValueArg<string> hmmdir_arg_, datadir_arg_, infile_arg_, outfile_arg_, cachefile_arg_, algorithm_arg_;
  ValueArg<float> hamming_fraction_cutoff_arg_;
  ValueArg<int> debug_arg_, n_best_events_arg_;
  SwitchArg chunk_cache_arg_, partition_arg_;

  // arguments read from csv input file
  map<string, vector<string> > strings_;
  map<string, vector<int> > integers_;
  map<string, vector<vector<string> > > str_lists_;
  map<string, vector<vector<double> > > float_lists_;
  set<string> str_headers_, int_headers_, str_list_headers_, float_list_headers_;

  // // extra values to cache command line args (TCLAP calls to ValuesConstraint::check() seem to be really slow
  // UPDATE hmm, didn't seem to help. leave it for the moment
  // string algorithm_;
  // int debug_;
};
}
#endif
