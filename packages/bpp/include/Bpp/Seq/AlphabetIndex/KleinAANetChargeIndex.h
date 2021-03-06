//
// File: KleinAANetChargeIndex.h
// Created by: Julien Dutheil
// Created on: Wed Aug 31 17:48 2005
//

/*
   Copyright or © or Copr. CNRS, (November 17, 2004)

   This software is a computer program whose purpose is to provide classes
   for sequences analysis.

   This software is governed by the CeCILL  license under French law and
   abiding by the rules of distribution of free software.  You can  use,
   modify and/ or redistribute the software under the terms of the CeCILL
   license as circulated by CEA, CNRS and INRIA at the following URL
   "http://www.cecill.info".

   As a counterpart to the access to the source code and  rights to copy,
   modify and redistribute granted by the license, users are provided only
   with a limited warranty  and the software's author,  the holder of the
   economic rights,  and the successive licensors  have only  limited
   liability.

   In this respect, the user's attention is drawn to the risks associated
   with loading,  using,  modifying and/or developing or reproducing the
   software by the user in light of its specific status of free software,
   that may mean  that it is complicated to manipulate,  and  that  also
   therefore means  that it is reserved for developers  and  experienced
   professionals having in-depth computer knowledge. Users are therefore
   encouraged to load and test the software's suitability as regards their
   requirements in conditions enabling the security of their systems and/or
   data to be ensured and,  more generally, to use and operate it in the
   same conditions as regards security.

   The fact that you are presently reading this means that you have had
   knowledge of the CeCILL license and that you accept its terms.
 */

#ifndef _KLEINAANETCHARGEINDEX_H_
#define _KLEINAANETCHARGEINDEX_H_

#include "AlphabetIndex1.h"
#include "../Alphabet/ProteicAlphabet.h"

namespace bpp
{
/**
 * @brief Charge of each amino acid.
 *
 * @code
 * Database: AAindex
 * Entry: KLEP840101
 *
 * H KLEP840101
 * D Net charge (Klein et al., 1984)
 * R LIT:1008055 PMID:6547351
 * A Klein, P., Kanehisa, M. and DeLisi, C.
 * T Prediction of protein function from sequence properties: Discriminant
 * analysis of a data base
 * J Biochim. Biophys. Acta 787, 221-226 (1984)
 * C ZIMJ680104    0.941
 * I    A/L     R/K     N/M     D/F     C/P     Q/S     E/T     G/W     H/Y     I/V
 *       0.      1.      0.     -1.      0.      0.     -1.      0.      0.      0.
 *       0.      1.      0.      0.      0.      0.      0.      0.      0.      0.
 * //
 * @endcode
 */
class KleinAANetChargeIndex :
  public AlphabetIndex1
{
private:
  std::vector<double> charge_;

public:
  KleinAANetChargeIndex() : charge_()
  {
    charge_.resize(20);
    charge_[ 0] =  0.; // A
    charge_[ 1] =  1.; // R
    charge_[ 2] =  0.; // N
    charge_[ 3] = -1.; // D
    charge_[ 4] =  0.; // C
    charge_[ 5] =  0.; // Q
    charge_[ 6] = -1.; // E
    charge_[ 7] =  0.; // G
    charge_[ 8] =  0.; // H
    charge_[ 9] =  0.; // I
    charge_[10] =  0.; // L
    charge_[11] =  1.; // K
    charge_[12] =  0.; // M
    charge_[13] =  0.; // F
    charge_[14] =  0.; // P
    charge_[15] =  0.; // S
    charge_[16] =  0.; // T
    charge_[17] =  0.; // W
    charge_[18] =  0.; // Y
    charge_[19] =  0.; // V
  }

  virtual ~KleinAANetChargeIndex() {}

  KleinAANetChargeIndex* clone() const { return new KleinAANetChargeIndex(); }

public:
  double getIndex(int state) const throw (BadIntException)
  {
    if (state < 0 || state > 19) throw BadIntException(state, "KleinAANetChargeIndex::getIndex(). Invalid state.", &AlphabetTools::PROTEIN_ALPHABET);
    return charge_[state];
  }

  double getIndex(const std::string& state) const throw (BadCharException)
  {
    return charge_[AlphabetTools::PROTEIN_ALPHABET.charToInt(state)];
  }

  std::vector<double>* getIndexVector() const { return new std::vector<double>(charge_); }

  const Alphabet* getAlphabet() const { return &AlphabetTools::PROTEIN_ALPHABET; }
};
} // end of namespace bpp.

#endif // _KLEINAANETCHARGEINDEX_H_

