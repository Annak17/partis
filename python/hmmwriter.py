import sys
import os
import re
import math
import collections
import yaml
from scipy.stats import norm
import csv
import utils
from opener import opener

# ----------------------------------------------------------------------------------------
def get_bin_list(values, bin_type):
    assert bin_type == 'all' or bin_type == 'empty' or bin_type == 'full'
    lists = {}
    lists['all'] = []
    lists['empty'] = []
    lists['full'] = []
    for bin_val, bin_contents in values.iteritems():
        lists['all'].append(bin_val)
        if bin_contents < utils.eps:
            lists['empty'].append(bin_val)
        else:
            lists['full'].append(bin_val)

    return sorted(lists[bin_type])

# ----------------------------------------------------------------------------------------
def find_full_bin(bin_val, full_bins, side):
    """
    Find the member of <full_bins> which is closest to <bin_val> on the <side>.
    NOTE if it can't find it, i.e. if <bin_val> is equal to or outside the limits of <full_bins>, returns the outermost value of <full_bins>
    """
    assert full_bins == sorted(full_bins)
    assert len(full_bins) > 0
    assert side == 'lower' or side == 'upper'

    if side == 'lower':
        nearest_bin = full_bins[0]
        for ib in full_bins:
            if ib < bin_val and ib > nearest_bin:
                nearest_bin = ib
    elif side == 'upper':
        nearest_bin = full_bins[-1]
        for ib in sorted(full_bins, reverse=True):
            if ib > bin_val and ib < nearest_bin:
                nearest_bin = ib

    return nearest_bin

# ----------------------------------------------------------------------------------------
def add_empty_bins(values):
    # add an empty bin between any full ones
    all_bins = get_bin_list(values, 'all')
    for ib in range(all_bins[0], all_bins[-1]):
        if ib not in values:
            values[ib] = 0.0

# ----------------------------------------------------------------------------------------
def interpolate_bins(values, n_max_to_interpolate, bin_eps, debug=False):
    """
    Interpolate the empty (less than utils.eps) bins in <values> if the neighboring full bins have less than <n_max_to_interpolate> entries,
    otherwise fill with <bin_eps>. NOTE there's some shenanigans if you have empty bins on the edges
    """
    if debug:
        print '---- interpolating with %d' % n_max_to_interpolate
        for x in sorted(values.keys()):
            print '    %3d %f' % (x, values[x])
    add_empty_bins(values)
    full_bins = get_bin_list(values, 'full')
    if debug:
        print '----'
        for x in sorted(values.keys()):
            print '     %3d %f' % (x, values[x])
    for empty_bin in get_bin_list(values, 'empty'):
        lower_full_bin = find_full_bin(empty_bin, full_bins, side='lower')
        upper_full_bin = find_full_bin(empty_bin, full_bins, side='upper')
        if n_max_to_interpolate == -1 or values[lower_full_bin] + values[upper_full_bin] < n_max_to_interpolate:
            lower_weight = 1.0 / max(1, abs(empty_bin - lower_full_bin))
            upper_weight = 1.0 / max(1, abs(empty_bin - upper_full_bin))
            values[empty_bin] = lower_weight*values[lower_full_bin] + upper_weight*values[upper_full_bin]
            values[empty_bin] /= lower_weight + upper_weight
        else:
            values[empty_bin] = bin_eps
    if debug:
        print '----'
        for x in sorted(values.keys()):
            print '     %3d %f' % (x, values[x])

# ----------------------------------------------------------------------------------------
class Track(object):
    def __init__(self, name, letters):
        self.name = name
        self.letters = letters  # should be a list

# ----------------------------------------------------------------------------------------
class State(object):
    def __init__(self, name):
        self.name = name
        self.transitions = {}
        self.emissions = {}  # partially implement emission to multiple tracks (I say 'partially' because I think I haven't written it into ham yet)
        self.pair_emissions = {}
        self.extras = {}  # any extra info you want to add

    def add_emission(self, track, emission_probs):  # NOTE we only allow one single (i.e. non-pair) emission a.t.m
        for letter in track.letters:
            assert letter in emission_probs
        assert 'track' not in self.emissions
        assert 'probs' not in self.emissions
        self.emissions['track'] = track.name
        self.emissions['probs'] = emission_probs

    def add_pair_emission(self, track, pair_emission_probs):  # NOTE we only allow one pair emission a.t.m
        for letter1 in track.letters:
            assert letter1 in pair_emission_probs
            for letter2 in track.letters:
                assert letter2 in pair_emission_probs[letter1]
        assert 'tracks' not in self.pair_emissions
        assert 'probs' not in self.pair_emissions
        self.pair_emissions['tracks'] = [track.name, track.name]
        self.pair_emissions['probs'] = pair_emission_probs

    def add_transition(self, to_name, prob):
        assert to_name not in self.transitions
        self.transitions[to_name] = prob

    def check(self):
        total = 0.0
        for _, prob in self.transitions.iteritems():
            assert prob >= 0.0
            total += prob
        assert utils.is_normed(total)

        if self.name == 'init':  # no emissions for 'init' state
            return

        total = 0.0
        for _, prob in self.emissions['probs'].iteritems():
            assert prob >= 0.0
            total += prob
        assert utils.is_normed(total)

        total = 0.0
        for letter1 in self.pair_emissions['probs']:
            for _, prob in self.pair_emissions['probs'][letter1].iteritems():
                assert prob >= 0.0
                total += prob
        assert utils.is_normed(total)

# ----------------------------------------------------------------------------------------
class HMM(object):
    def __init__(self, name, tracks):
        self.name = name
        self.tracks = tracks
        self.states = []
        self.extras = {}  # any extra info you want to add
    def add_state(self, state):
        state.check()
        self.states.append(state)

# ----------------------------------------------------------------------------------------
class HmmWriter(object):
    def __init__(self, base_indir, outdir, gene_name, naivety, germline_seq):
        self.indir = base_indir
        self.precision = '16'  # number of digits after the decimal for probabilities. TODO increase this?
        self.eps = 1e-6  # TODO I also have an eps defined in utils
        self.min_occurences = 10
        self.n_max_to_interpolate = 20

        self.insert_mute_prob = 0.0
        self.mean_mute_freq = 0.0

        self.outdir = outdir
        self.region = utils.get_region(gene_name)
        self.naivety = naivety
        self.germline_seq = germline_seq
        self.smallest_entry_index = -1  # keeps track of the first state that has a chance of being entered from init -- we want to start writing (with add_internal_state) from there

        # self.insertions = [ insert for insert in utils.index_keys if re.match(self.region + '._insertion', insert) or re.match('.' + self.region + '_insertion', insert)]  OOPS that's not what I want to do
        if self.region == 'v':
            self.insertions = ['fv', ]
        elif self.region == 'd':
            self.insertions = ['vd', ]
        elif self.region == 'j':
            self.insertions = ['dj', 'jf']

        self.erosion_probs = {}
        self.insertion_probs = {}
        self.mute_freqs = {}

        self.n_occurences = utils.read_overall_gene_probs(self.indir, only_gene=gene_name, normalize=False)  # how many times did we observe this gene in data?
        replacement_genes = None
        if self.n_occurences < self.min_occurences:  # if we didn't see it enough, average over all the genes that find_replacement_genes() gives us
            print '    only saw it %d times, use info from other genes' % self.n_occurences
            replacement_genes = utils.find_replacement_genes(self.indir, gene_name, self.min_occurences, single_gene=False, debug=True)

        self.read_erosion_info(gene_name, replacement_genes)  # try this exact gene, but...

        self.read_insertion_info(gene_name, replacement_genes)

        if self.naivety == 'M':  # mutate if not naive
            self.read_mute_info(gene_name, replacement_genes)  # TODO make sure that the overall 'normalization' of the mute freqs here agrees with the branch lengths in the tree simulator in recombinator. I kinda think it doesn't

        self.track = Track('nukes', list(utils.nukes))
        self.saniname = utils.sanitize_name(gene_name)  # TODO make this not a member variable to make absolutely sure you don't confuse gene_name and replacement_gene
        self.hmm = HMM(self.saniname, {'nukes':list(utils.nukes)})  # pass the track as a dict rather than a Track object to keep the yaml file a bit more readable
        self.hmm.extras['gene_prob'] = max(self.eps, utils.read_overall_gene_probs(self.indir, only_gene=gene_name))  # if we really didn't see this gene at all, take pity on it and kick it an eps

    # ----------------------------------------------------------------------------------------
    def write(self):
        self.add_states()
        assert os.path.exists(self.outdir)
        with opener('w')(self.outdir + '/' + self.saniname + '.yaml') as outfile:
            yaml.dump(self.hmm, outfile, width=150)

    # ----------------------------------------------------------------------------------------
    def add_states(self):
        self.add_init_state()
        # then left side insertions
        for insertion in self.insertions:
            if insertion == 'jf':
                continue
            self.add_lefthand_insert_state(insertion)
        # then write internal states
        assert self.smallest_entry_index >= 0  # should have been set in add_region_entry_transitions
        for inuke in range(self.smallest_entry_index, len(self.germline_seq)):
            self.add_internal_state(inuke)
        # and finally right side insertions
        if self.region == 'j':
            self.add_righthand_insert_state()

    # ----------------------------------------------------------------------------------------
    def add_init_state(self):
        init_state = State('init')
        lefthand_insertion = self.insertions[0]
        assert 'jf' not in lefthand_insertion
        self.add_region_entry_transitions(init_state, lefthand_insertion)
        self.hmm.add_state(init_state)

    # ----------------------------------------------------------------------------------------
    def add_lefthand_insert_state(self, insertion):
        insert_state = State('insert_left')
        self.add_region_entry_transitions(insert_state, insertion)  # TODO allow d region to be entirely eroded?
        self.add_emissions(insert_state)
        self.hmm.add_state(insert_state)

    # ----------------------------------------------------------------------------------------
    def add_internal_state(self, inuke):
        # arbitrarily replace ambiguous nucleotides with 'A' TODO figger out something better
        germline_nuke = self.germline_seq[inuke]
        if germline_nuke == 'N' or germline_nuke == 'Y':
            print '\n    WARNING replacing %s with A' % germline_nuke
            germline_nuke = 'A'

        # initialize
        state = State('%s_%d' % (self.saniname, inuke))
        state.extras['germline'] = germline_nuke

        # transitions
        exit_probability = self.get_exit_probability(inuke) # probability of ending this region here, i.e. excising the rest of the germline gene
        distance_to_end = len(self.germline_seq) - inuke - 1
        if distance_to_end > 0:  # if we're not at the end of this germline gene, add a transition to the next state
            state.add_transition('%s_%d' % (self.saniname, inuke+1), 1.0 - exit_probability)
        if exit_probability >= utils.eps or distance_to_end == 0:  # add transition to 'end' or 'insert_right' if there's a decent chance of eroding to here, or if we're at the end of the germline sequence
            self.add_region_exit_transitions(state, exit_probability)

        # emissions
        self.add_emissions(state, inuke=inuke, germline_nuke=germline_nuke)

        self.hmm.add_state(state)

    # ----------------------------------------------------------------------------------------
    def add_righthand_insert_state(self):
        insert_state = State('insert_right')
        self_transition_prob = 1.0 - self.get_inverse_insert_length('jf')
        if self_transition_prob < 0.0:  # if mean mean insertion length is less than zero, we can no longer use 1/mean_length as a probability
            # TODO do something more permanent
            # TODO at least use more than the second bin in the numerator
            assert 0 in self.insertion_probs['jf']
            assert 1 in self.insertion_probs['jf']
            self_transition_prob = float(self.insertion_probs['jf'][1]) / self.insertion_probs['jf'][0]
            assert self_transition_prob >= 0.0 and self_transition_prob <= 1.0
            print '    WARNING using insert self-transition probability hack p(1) / p(0) = %f / %f = %f' % (self.insertion_probs['jf'][1], self.insertion_probs['jf'][0], self_transition_prob)
        insert_state.add_transition('insert_right', self_transition_prob)
        insert_state.add_transition('end', 1.0 - self_transition_prob)
        self.add_emissions(insert_state)
        self.hmm.add_state(insert_state)

    # ----------------------------------------------------------------------------------------
    def read_erosion_info(self, this_gene, approved_genes=None):
        # TODO in cases where the bases which are eroded are the same as those inserted (i.e. cases that *suck*) I seem to *always* decide on the choice with the shorter insertion. not good!
        # NOTE that d erosion lengths depend on each other... but I don't think that's modellable with an hmm. At least for the moment we integrate over the other erosion
        if approved_genes == None:
            approved_genes = [this_gene,]
        genes_used = set()
        for erosion in utils.real_erosions + utils.effective_erosions:
            if erosion[0] != self.region:
                continue
            self.erosion_probs[erosion] = {}
            deps = utils.column_dependencies[erosion + '_del']
            with opener('r')(self.indir + '/' + utils.get_parameter_fname(column=erosion + '_del', deps=deps)) as infile:
                reader = csv.DictReader(infile)
                for line in reader:
                    # first see if we want to use this line (if <region>_gene isn't in the line, this erosion doesn't depend on gene version)
                    if self.region + '_gene' in line and line[self.region + '_gene'] not in approved_genes:  # NOTE you'll need to change this if you want it to depend on another region's genes
                        continue
                    # the skip nonsense erosions that're too long for this gene, but were ok for another
                    if int(line[erosion + '_del']) >= len(self.germline_seq):
                        continue

                    # then add in this erosion's counts
                    n_eroded = int(line[erosion + '_del'])
                    if n_eroded not in self.erosion_probs[erosion]:
                        self.erosion_probs[erosion][n_eroded] = 0.0
                    self.erosion_probs[erosion][n_eroded] += float(line['count'])

                    if self.region + '_gene' in line:
                        genes_used.add(line[self.region + '_gene'])

            assert len(self.erosion_probs[erosion]) > 0

            # do some smoothingy things NOTE that we normalize *after* interpolating
            if erosion in utils.real_erosions:  # for real erosions, don't interpolate if we lots of information about neighboring bins (i.e. we're pretty confident this bin should actually be zero)
                n_max = self.n_max_to_interpolate
            else:  # for fake erosions, always interpolate
                n_max = -1
            # print '   interpolate erosions'
            interpolate_bins(self.erosion_probs[erosion], n_max, bin_eps=self.eps)

            # and finally, normalize
            total = 0.0
            for _, val in self.erosion_probs[erosion].iteritems():
                total += val

            test_total = 0.0
            for n_eroded in self.erosion_probs[erosion]:
                self.erosion_probs[erosion][n_eroded] /= total
                test_total += self.erosion_probs[erosion][n_eroded]
            assert utils.is_normed(test_total)

        if len(genes_used) > 1:  # if length is 1, we will have just used the actual gene
            print '    erosions used:', ' '.join(genes_used)

    # ----------------------------------------------------------------------------------------
    def read_insertion_info(self, this_gene, approved_genes=None):
        if approved_genes == None:  # if we aren't explicitly passed a list of genes to use, we just use the gene for which we're actually writing the hmm
            approved_genes = [this_gene,]

        for insertion in self.insertions:
            self.insertion_probs[insertion] = {}
            deps = utils.column_dependencies[insertion + '_insertion']
            genes_used = set()
            with opener('r')(self.indir + '/' + utils.get_parameter_fname(column=insertion + '_insertion', deps=deps)) as infile:
                reader = csv.DictReader(infile)
                for line in reader:
                    # first see if we want to use this line (if <region>_gene isn't in the line, this erosion doesn't depend on gene version)
                    if self.region + '_gene' in line and line[self.region + '_gene'] not in approved_genes:  # NOTE you'll need to change this if you want it to depend on another region's genes
                        continue

                    # then add in this insertion's counts
                    n_inserted = 0
                    n_inserted = int(line[insertion + '_insertion'])
                    if n_inserted not in self.insertion_probs[insertion]:
                        self.insertion_probs[insertion][n_inserted] = 0.0
                    self.insertion_probs[insertion][n_inserted] += float(line['count'])

                    if self.region + '_gene' in line:
                        genes_used.add(line[self.region + '_gene'])

            assert len(self.insertion_probs[insertion]) > 0

            # print '   interpolate insertions'
            interpolate_bins(self.insertion_probs[insertion], self.n_max_to_interpolate, bin_eps=self.eps)  # NOTE that we normalize *after* this

            assert 0 in self.insertion_probs[insertion] and len(self.insertion_probs[insertion]) >= 2  # all hell breaks loose lower down if we haven't got shit in the way of information

            # and finally, normalize
            total = 0.0
            for _, val in self.insertion_probs[insertion].iteritems():
                total += val
            test_total = 0.0
            for n_inserted in self.insertion_probs[insertion]:
                self.insertion_probs[insertion][n_inserted] /= total
                test_total += self.insertion_probs[insertion][n_inserted]
            assert utils.is_normed(test_total)

            if 0 not in self.insertion_probs[insertion] or self.insertion_probs[insertion][0] == 1.0:
                print 'ERROR cannot have all or none of the probability mass in the zero bin:', self.insertion_probs[insertion]
                assert False

        if len(genes_used) > 1:  # if length is 1, we will have just used the actual gene
            print '    insertions used:', ' '.join(genes_used)

    # ----------------------------------------------------------------------------------------
    def read_mute_info(self, this_gene, approved_genes=None):
        if approved_genes == None:
            approved_genes = [this_gene,]
        observed_freqs = {}  # of the form {0:(0.4, 0.38, 0.42), ...} (for position 0 with freq 0.4 with uncertainty 0.02)
        for gene in approved_genes:
            mutefname = self.indir + '/mute-freqs/' + utils.sanitize_name(gene) + '.csv'
            if not os.path.exists(mutefname):
                continue
            with opener('r')(mutefname) as mutefile:
                reader = csv.DictReader(mutefile)
                for line in reader:
                    pos = int(line['position'])
                    freq = float(line['mute_freq'])
                    lo_err = float(line['lo_err'])  # NOTE lo_err in the file is really the lower *bound*
                    hi_err = float(line['hi_err'])  #   same deal
                    assert freq >= 0.0 and lo_err >= 0.0 and hi_err >= 0.0  # you just can't be too careful
                    if freq < utils.eps or abs(1.0 - freq) < utils.eps:  # if <freq> too close to 0 or 1, replace it with the midpoint of its uncertainty band
                        freq = 0.5 * (lo_err + hi_err)
                    if pos not in observed_freqs:
                        observed_freqs[pos] = []
                    observed_freqs[pos].append({'freq':freq, 'err':max(abs(freq-lo_err), abs(freq-hi_err))})

        overall_total, overall_sum_of_weights = 0.0, 0.0
        for pos in observed_freqs:
            total, sum_of_weights = 0.0, 0.0
            for obs in observed_freqs[pos]:
                assert obs['err'] > 0.0
                weight = 1.0 / obs['err']
                total += weight * obs['freq']
                sum_of_weights += weight
            assert sum_of_weights > 0.0
            mean_freq = total / sum_of_weights
            self.mute_freqs[pos] = mean_freq
            overall_total += total
            overall_sum_of_weights += sum_of_weights

        self.mean_mute_freq = overall_total / overall_sum_of_weights
        self.insert_mute_prob = self.mean_mute_freq

    # ----------------------------------------------------------------------------------------
    def get_inverse_insert_length(self, insertion):
        mean_length = self.get_mean_insert_length(insertion)
        inverse_length = 0.0
        if mean_length > 0.0:
            inverse_length = 1.0 / mean_length
        if mean_length < 1.0:  # TODO do something more permanent here
            print '    WARNING small mean insert length %f' % mean_length

        return inverse_length

    # ----------------------------------------------------------------------------------------
    def get_non_zero_insertion_prob(self, state_name, insertion):
        if state_name == 'init':
            return 1.0 - self.insertion_probs[insertion][0]
        elif state_name == 'insert_left':  # we want the prob of *leaving* the insert state to be 1/insertion_length, so multiply all the region entry probs (below) by this
            inverse_length = self.get_inverse_insert_length(insertion)
            assert inverse_length <= 1.0
            return 1.0 - inverse_length  # set the prob of *remaining* in the insert state to [1 - 1/mean_insert_length]
        else:
            assert False

    # ----------------------------------------------------------------------------------------
    def add_region_entry_transitions(self, state, insertion):
        """
        Add transitions *into* the v, d, or j regions. Called from either the 'init' state or the 'insert' state.
        For v, this is (mostly) the prob that the read doesn't extend all the way to the left side of the v gene.
        For d and j, this is (mostly) the prob to actually erode on the left side.
        The two <mostly>s are there because in both cases, we're starting from *approximate* smith-waterman alignments, so we need to add some fuzz in case the s-w is off.
        For insert states, 
        """
        assert 'jf' not in insertion  # need these to only be *left*-hand insertions
        assert state.name == 'init' or state.name == 'insert_left'

        non_zero_insertion_prob = 0.0  # Prob of a non-zero-length insertion (i.e. prob to *not* go directly into the region)
                                       # The sum of the region entry probs must be (1 - non_zero_insertion_prob) for d and j
                                       # (i.e. such that [prob of transitions to insert] + [prob of transitions *not* to insert] is 1.0)

        # first add transitions to the insert state
        non_zero_insertion_prob = self.get_non_zero_insertion_prob(state.name, insertion)
        # If this is an 'init' state, we add a transition to 'insert' with probability the observed probability of a non-zero insertion
        # Whereas if this is an 'insert' state, we add a *self*-transition with probability 1/<mean observed insert length>
        state.add_transition('insert_left', non_zero_insertion_prob)

        # then add transitions to the region's internal states
        total = 0.0
        for inuke in range(len(self.germline_seq)):
            erosion = self.region + '_5p'
            erosion_length = inuke
            if erosion_length in self.erosion_probs[erosion]:
                prob = self.erosion_probs[erosion][erosion_length]
                total += prob * (1.0 - non_zero_insertion_prob)
                if non_zero_insertion_prob != 1.0:  # only add the line if there's a chance of zero-length insertion
                    state.add_transition('%s_%d' % (self.saniname, inuke), prob * (1.0 - non_zero_insertion_prob))
                    if self.smallest_entry_index == -1 or inuke < self.smallest_entry_index:
                        self.smallest_entry_index = inuke
        assert non_zero_insertion_prob == 1.0 or utils.is_normed(total / (1.0 - non_zero_insertion_prob))

    # ----------------------------------------------------------------------------------------
    def add_region_exit_transitions(self, state, exit_probability):
        non_zero_insertion_prob = 0.0
        if self.region == 'j':  # add transition to the righthand insert state with probability the observed probability of a non-zero insertion (times the exit_probability)
            non_zero_insertion_prob = 1.0 - self.insertion_probs['jf'][0]
            state.add_transition('insert_right', non_zero_insertion_prob * exit_probability)

        state.add_transition('end', (1.0 - non_zero_insertion_prob) * exit_probability)  # and add a transition to 'end' with the complement, to allow zero-length insertions

    # ----------------------------------------------------------------------------------------
    def get_exit_probability(self, inuke):
        """
        Prob of exiting the chain of states for this region at <inuke>.
        In other words, what is the prob that we will erode all the bases to the right of <inuke>.
        """
        distance_to_end = len(self.germline_seq) - inuke - 1
        if distance_to_end == 0:  # last state has to exit region
            return 1.0
        erosion = self.region + '_3p'
        erosion_length = distance_to_end
        if erosion_length in self.erosion_probs[erosion]:
            prob = self.erosion_probs[erosion][erosion_length]
            if prob > utils.eps:
                return prob
            else:
                return 0.0
        else:
            return 0.0

    # ----------------------------------------------------------------------------------------
    def get_mean_insert_length(self, insertion):
        total, n_tot = 0.0, 0.0
        for length, count in self.insertion_probs[insertion].iteritems():
            total += count*length
            n_tot += count
        if n_tot == 0.0:
            return -1
        else:
            return total / n_tot

    # ----------------------------------------------------------------------------------------
    def get_emission_prob(self, nuke1, nuke2='', is_insert=True, inuke=-1, germline_nuke=''):
        assert nuke1 in utils.nukes
        assert nuke2 == '' or nuke2 in utils.nukes
        prob = 1.0
        if is_insert:
            assert self.insert_mute_prob != 0.0
            if nuke2 == '':  # single (non-pair) emission
                prob = 1./len(utils.nukes)
            else:
                if nuke1 == nuke2:
                    prob = (1. - self.insert_mute_prob) / 4
                else:
                    prob = self.insert_mute_prob / 12
        else:
            assert inuke >= 0
            assert germline_nuke != ''

            # first figure out the mutation frequency we're going to use
            mute_freq = self.mean_mute_freq
            if inuke in self.mute_freqs:  # if we found this base in this gene version in the data parameter file
                mute_freq = self.mute_freqs[inuke]

            # then calculate the probability
            if nuke2 == '':
                assert mute_freq != 1.0 and mute_freq != 0.0
                if nuke1 == germline_nuke:  # TODO note that if mute_freq is 1.0 this gives zero
                    prob = 1.0 - mute_freq
                else:
                    prob = mute_freq / 3.0  # TODO take into account different frequency of going to different bases
            else:  # TODO change this back to the commented block
                for nuke in (nuke1, nuke2):
                    if nuke == germline_nuke:
                        prob *= 1.0 - mute_freq
                    else:
                        prob *= mute_freq / 3.0
                # cryptic_factor_from_normalization = (math.sqrt(3.)*math.sqrt(-8.*mute_freq**2 + 16.*mute_freq + 27.) - 9.) / 12.
                # if nuke1 == germline_nuke and nuke2 == germline_nuke:
                #     prob = (1.0 - mute_freq)**2
                # elif nuke1 == nuke2 and nuke1 != germline_nuke:  # assume this requires *one* mutation event (i.e. ignore higher-order terms, I think)
                #     prob = cryptic_factor_from_normalization
                # elif nuke1 == germline_nuke or nuke2 == germline_nuke:
                #     prob = cryptic_factor_from_normalization
                # else:
                #     prob = cryptic_factor_from_normalization**2

        return prob

    # ----------------------------------------------------------------------------------------
    def add_emissions(self, state, inuke=-1, germline_nuke=''):
        # first add single emission
        emission_probs = {}
        total = 0.0
        for nuke in utils.nukes:
            emission_probs[nuke] = self.get_emission_prob(nuke, is_insert=('insert' in state.name), inuke=inuke, germline_nuke=germline_nuke)
            total += emission_probs[nuke]
        if math.fabs(total - 1.0) >= self.eps:
            print 'ERROR emission not normalized in state %s in %s (%f)' % (state.name, 'X', total)  #utils.color_gene(gene_name), total)
            assert False
        state.add_emission(self.track, emission_probs)

        # then the pair emission
        pair_emission_probs = {}
        total = 0.0
        for nuke1 in utils.nukes:
            pair_emission_probs[nuke1] = {}
            for nuke2 in utils.nukes:
                pair_emission_probs[nuke1][nuke2] = self.get_emission_prob(nuke1, nuke2, is_insert=('insert' in state.name), inuke=inuke, germline_nuke=germline_nuke)
                total += pair_emission_probs[nuke1][nuke2]
        if math.fabs(total - 1.0) >= self.eps:
            print 'ERROR pair emission not normalized in state %s in %s (%f)' % (state.name, 'X', total)  #utils.color_gene(gene_name), total)
            assert False
        state.add_pair_emission(self.track, pair_emission_probs)
