//
//  new_trellis.h
//  StochHMM
//
//  Created by Paul Lott on 11/13/12.
//  Copyright (c) 2012 Korf Lab, Genome Center, UC Davis, Davis, CA. All rights reserved.
//

#ifndef __StochHMM__new_trellis__
#define __StochHMM__new_trellis__

#include <iostream>
#include <vector>
#include <stdint.h>
#include <vector>
#include <string>
#include <fstream>
#include <bitset>
#include "stochTypes.h"
#include "sequences.h"
#include "hmm.h"
#include "traceback_path.h"
#include "stochMath.h"


namespace StochHMM {

//	struct tb_score{
//		float score;
//		int16_t tb_ptr;
//	};
	
	
	
	class stochTable{
	public:
		
		struct stoch_value{
			stoch_value(uint16_t id, uint16_t prev, float p): state_id(id), state_prev(prev), prob(p){}
			uint16_t state_id;
			uint16_t state_prev;
			float prob;
		};
		
		
		stochTable(size_t);
		~stochTable();
		void push(size_t pos, size_t st, size_t st_to, float val);
		void print();
		void finalize();
		
	private:
		size_t last_position;
		std::vector<stoch_value>* state_val;
		std::vector<size_t>* position;
	};
	
	
	typedef std::vector<std::vector<uint16_t> > int_2D;
	typedef std::vector<std::vector<float> > float_2D;
	typedef std::vector<std::vector<std::vector<uint16_t> > > int_3D;
	typedef std::vector<std::vector<std::vector<float> > > float_3D;

	class trellis{
	public:
		trellis();
		trellis(model* h , sequences* sqs);
		~trellis();
		void reset();
		
		void viterbi();
		void viterbi(model* h, sequences* sqs);
		
		void forward();
		void forward(model* h, sequences* sqs);
		
		void forward_viterbi();
		void forward_viterbi(model* h, sequences* sqs);
		
		void backward();
		void backward(model* h, sequences* sqs);
		
		void posterior();
		void posterior(model* h, sequences* sqs);
		
		void stochastic_viterbi();
		void stochastic_viterbi(model* h, sequences* sqs);
		
		void stochastic_forward();
		void stochastic_forward(model* h, sequences *sqs);
		
		void nth_viterbi();
		void nth_viterbi(model* h, sequences *sqs);
		
		void traceback(traceback_path& path);
        void traceback(traceback_path&,size_t);
		void traceback_stoch_forward(multiTraceback&,size_t);
		void traceback_stoch_viterbi(multiTraceback&,size_t);
		void traceback_nth_viterbi(multiTraceback&);
		
		void baum_welch();
		
		inline bool store(){return store_values;}
		inline void store(bool val){store_values=val; return;}

		void print();
		std::string stringify();
		void export_trellis(std::ifstream&);
		void export_trellis(std::string& file);
		inline model* get_model(){return hmm;}
		
	private:
		double getEndingTransition(size_t);
        double getTransition(state* st, size_t trans_to_state, size_t sequencePosition);
        size_t get_explicit_duration_length(transition* trans, size_t sequencePosition);
        double exFuncTraceback(transitionFuncParam*);
		
		
		model* hmm;		//HMM model
        sequences* seqs; //Digitized Sequences
		
		size_t state_size;	//Number of States
		size_t seq_size;	//Length of Sequence
		
		trellisType type;
		
		bool store_values;
		bool exDef_defined;
		
		//Traceback Tables
		int_2D*		traceback_table;          //Simple traceback table
		int_3D*		nth_traceback;      //Nth-Viterbi traceback table
		stochTable* stochastic_table;
		
		//Score Tables
		float_2D*	viterbi_score;      //Storing viterbi scores
		float_2D*	forward_score;      //Storing Forward scores
		float_2D*	backward_score;     //Storing Backward scores
		float_2D*	posterior_score;			//Store posterior scores
		
		//Ending Cells
		double   ending_viterbi_score;
		uint16_t ending_viterbi_tb;
		
		double   ending_posterior;

//		std::vector<tb_score>*    ending_stoch_tb;
//		std::vector<tb_score>*    ending_nth_viterbi;
		
		//Cells used for calculating the Viterbi
		std::vector<double>* viterbi_current;
		std::vector<double>* viterbi_previous;
		
		//Array used for calculating the Backward Scores
		std::vector<double>* backward_current;
		std::vector<double>* backward_previous;
		
		std::vector<size_t>* explicit_duration_current;
		std::vector<size_t>* explicit_duration_previous;
		
		std::vector<double>* swap_ptr;
	};
	
}

#endif /* defined(__StochHMM__new_trellis__) */
