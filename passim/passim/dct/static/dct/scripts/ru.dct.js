var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      // ru.basic.init_events();
      // ru.basic.init_typeahead();
      ru.dct.load_dct();
      ru.dct.init_selection();
      // Initialize Bootstrap popover
      // Note: this is used when hovering over the question mark button
      $('[data-toggle="popover"]').popover();
    });
  });
})(django.jQuery);


// based on the type, action will be loaded

// var $ = django.jQuery.noConflict();

var ru = (function ($, ru) {
  "use strict";

  ru.dct = (function ($, config) {
    // Define variables for ru.basic here
    var loc_divErr = "passim_err",
        loc_urlStore = "",      // Keep track of URL to be shown
        loc_progr = [],         // Progress tracking
        loc_columnTh = null,    // TH being dragged
        loc_params = "",        // DCT parameters
        loc_ssglists = null,    // The object with the DCT information
        loc_colwrap = [],       // Column wrapping
        loc_dctdata = [],
        loc_dragDst = null,     // Destination of the dragging
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        loc_bManuSaved = false,
        loc_keyword = [],           // Keywords that can belong to a sermongold or a sermondescr
        loc_language = [],
        KEYS = {
          BACKSPACE: 8, TAB: 9, ENTER: 13, SHIFT: 16, CTRL: 17, ALT: 18, ESC: 27, SPACE: 32, PAGE_UP: 33, PAGE_DOWN: 34,
          END: 35, HOME: 36, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, DELETE: 46
        },
        loc_dctTooltip = [
          { "label": "Gryson/Clavis", "key": "siglist" },
          { "label": "Author", "key": "author" },
          { "label": "PASSIM code", "key": "code" },
          { "label": "Incipit", "key": "incipit" },
          { "label": "Explicit", "key": "explicit" },
          { "label": "Part of HC[s]", "key": "hcs" },
          { "label": "SGs in equality set", "key": "sgcount" },
          { "label": "Links to other SSGs", "key": "ssgcount" },
        ],
        loc_dctTooltipCollection = [
          { "label": "Name",        "key": "name" },
          { "label": "Description", "key": "descr" },
        ],
        loc_dctTooltipAdditional = [
          { "label": "Attributed author", "key": "srm_author" },
          { "label": "Section title",     "key": "srm_sectiontitle" },
          { "label": "Lectio",            "key": "srm_lectio" },
          { "label": "Title",             "key": "srm_title" },
          { "label": "Incipit",           "key": "srm_incipit" },
          { "label": "Explicit",          "key": "srm_explicit" },
          { "label": "Postscriptum",      "key": "srm_postscriptum" },
          { "label": "Feast",             "key": "srm_feast" },
          { "label": "Bible reference",   "key": "srm_bibleref" },
          { "label": "Cod. notes",        "key": "srm_codnotes" },
          { "label": "Notes",             "key": "srm_notes" },
          { "label": "Keywords",          "key": "kws" },
        ],
        dummy = 1;

    // Private methods specification
    var private_methods = {
      /**
       * aaaaaaNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      aaaaaaNotVisibleFromOutside: function () {
        return "something";
      },
      
      copyToClipboard: function(elem) {
        // create hidden text element, if it doesn't already exist
        var targetId = "_hiddenCopyText_";
        var elConfirm = "";
        var isInput = "";
        var origSelectionStart, origSelectionEnd;

        try {
          // Get to the right element
          if (elem.tagName === "A") {
            elem = $(elem).closest("div").find("textarea").first().get(0);
          }
          isInput = elem.tagName === "INPUT" || elem.tagName === "TEXTAREA";
          if (isInput) {
            // can just use the original source element for the selection and copy
            target = elem;
            origSelectionStart = elem.selectionStart;
            origSelectionEnd = elem.selectionEnd;
          } else {
            // must use a temporary form element for the selection and copy
            target = document.getElementById(targetId);
            if (!target) {
              var target = document.createElement("textarea");
              target.style.position = "absolute";
              target.style.left = "-9999px";
              target.style.top = "0";
              target.id = targetId;
              document.body.appendChild(target);
            }
            target.textContent = elem.textContent;
          }
          // select the content
          var currentFocus = document.activeElement;
          target.focus();
          target.setSelectionRange(0, target.value.length);

          // copy the selection
          var succeed;
          try {
            succeed = document.execCommand("copy");
            console.log("Copied: " + target.value);
            elConfirm = $(elem).closest("div").find(".clipboard-confirm").first();
            $(elConfirm).html("Copied!");
            setTimeout(function () {
              $(elConfirm).fadeOut().empty();
            }, 4000);
          } catch (e) {
            succeed = false;
            console.log("Could not copy");
          }
          // restore original focus
          if (currentFocus && typeof currentFocus.focus === "function") {
            currentFocus.focus();
          }

          if (isInput) {
            // restore prior selection
            elem.setSelectionRange(origSelectionStart, origSelectionEnd);
          } else {
            // clear temporary content
            target.textContent = "";
          }
          
          return succeed;
        } catch (ex) {
          private_methods.errMsg("copyToClipboard", ex);
          return "";
        }

      },

      /** 
       *  createDiv - needed for resizableGrid
       */
      createDiv: function (height, colidx) {
        var div = document.createElement('div');
        div.style.top = 0;
        div.style.right = 0;
        div.style.width = '5px';
        div.style.position = 'absolute';
        div.style.cursor = 'col-resize';
        div.style.userSelect = 'none';

        // The table height determines how large the line is going to be
        div.style.height = height + 'px';
        // Set one custom attribut: the column index
        $(div).attr("colidx", colidx.toString());
        // REturn the div that has been made
        return div;
      },

      /** 
       *  colwrap_switch - switch a column on or off
       */
      colwrap_switch: function (colnum, set) {
        var lColWrap = null,
            elW = null,
            idx = -1;

        try {
          // Get the current value
          idx = loc_colwrap.indexOf(colnum);
          if (set) {
            if (idx < 0) {
              loc_colwrap.push(colnum);
            }
          } else {
            if (idx >= 0) {
              loc_colwrap.splice(idx, 1);
            }
          }
          // Set the correct 'w' parameter
          elW = document.getElementsByName("w");
          $(elW).val(JSON.stringify(loc_colwrap));
        } catch (ex) {
          private_methods.errMsg("colwrap_switch", ex);
          return "";
        }
      },

      /** 
        *  dct_author - Get the name of the (attributed) author
        */
      dct_author: function (oSsgItem, bFull) {
        var i = 0,
            sText = "",
            keys = ["srm_author", "author"];

        try {
          // Try the keys in turn
          for (i = 0; i < keys.length; i++) {
            if (keys[i] in oSsgItem) {
              sText = oSsgItem[keys[i]];
              if (sText === null) {
                sText = "";
              }
              break;
            }
          }
          if (bFull === undefined || !bFull) {
            // Abbreviate the text of the author
            sText = ". " + sText.substring(0, 5) + "...";
          }

          // Combine the html
          return sText;
        } catch (ex) {
          private_methods.errMsg("private/dct_author", ex);
        }
      },

      /** 
        *  dct_getdata - 
        *     Get the DCT data as stringified JSON
        */
      dct_getdata: function () {
        var sData = "",
            oRow = null,
            data = [],
            i = 0,
            view_mode = "";

        try {
          view_mode = loc_params['view_mode'];
          // Copy all data that should be included
          for (i = 0; i < loc_dctdata.length; i++) {
            oRow = loc_dctdata[i];
            if (oRow['match'] === true || view_mode === "all") {
              data.push(oRow['row']);
            }
          }
          sData = JSON.stringify(data);
          return sData;
        } catch (ex) {
          private_methods.errMsg("dct_getdata", ex);
          return "[]";
        }
      },

      /** 
       *  dct_highlight - Highlight or reset a particular row
       */
      dct_highlight: function (elStart) {
        var elRow = null;

        try {
          // Get the row
          elRow = $(elStart).closest("tr");
          // Action depends on whether the highlighting is there or not
          if ($(elRow).hasClass("dct-highlight")) {
            // REmove it
            $(elRow).removeClass("dct-highlight");
          } else {
            // Add it
            $(elRow).addClass("dct-highlight");
          }
        } catch (ex) {
          private_methods.errMsg("dct_highlight", ex);
        }
      },

      /** 
       *  dct_remaining_ssgs - Get a list of SSG-ids that have not been dealt with in the pivot_col
       */
      dct_remaining_ssgs: function(ssglists, pivot_col, dealt_with) {
        var lst_remaining = [],
            i = 0,
            row = 0,
            ssg = 0,
            ssglist = null,
            oSsgItem = null;

        try {

          // Need to walk all lists
          for (i = 0; i < ssglists.length; i++) {
            // Check if this is not the pivot list
            if (i !== pivot_col) {
              // Okay, this is not the pivot list: walk all SSGs that do *not* occur in the pivot list
              ssglist = ssglists[i]['ssglist'];
              for (row=0; row < ssglist.length; row++) {
                // Get details of this SSG
                oSsgItem = ssglist[row];
                // Get this SSG id
                ssg = oSsgItem.super;
                // Check if this SSG has already been dealt with
                if (dealt_with.indexOf(ssg) === -1) {
                  // Add the *object* to the list of objects to be treated
                  lst_remaining.push(oSsgItem);
                }
              }

            }
          }
          // Sort the remainder list
          lst_remaining.sort(function (a, b) {
            var retval = 0;

            if (a.order > b.order) {
              retval = 1;
            } else if (a.order === b.order) {
              retval =  (a.sig > b.sig) ? 1 : -1;
            } else {
              retval = -1;
            }
            return retval;
          });
          //lst_remaining.sort(
          //  (a, b) => (a.order > b.order ? 1 : (a.sig > b.sig ? 1 : -1))
          //  );
          // Return the list that we have ben building up
          return lst_remaining;
        } catch (ex) {
          private_methods.errMsg("dct_remaining_ssgs", ex);
          // Return empty list
          return [];
        }
      },

      /** 
       *  dct_row_combine -  Walk through all the other lists, finding this SSG
       */
      dct_row_combine: function(ssglists, pivot_col, oSsgThis, rowcolor, bShowPivot, lst_exclude) {
        var oBack = {'error': false},
            oSsgItem = null,
            i = 0,
            j = 0,
            order = 0,
            ssg = 0,
            siglist = [],
            sUrl = "",
            ssglist = null,
            sClass = "",
            bFound = false,
            datarow = [],
            html_row = [];

        try {
          // Start creating this row
          if ("siglist" in oSsgThis) { siglist = oSsgThis.siglist; }
          if ("url" in oSsgThis) { sUrl = oSsgThis.url; }
          html_row.push("<tr class='" + rowcolor +
            "'><td class='fixed-side fixed-col0 tdnowrap'><span class='clickable'><a class='nostyle' " +
            " data-toggle='tooltip' data-tooltip='dct-hover' href='" +
            sUrl + "' title='" + private_methods.dct_tooltip(oSsgThis, 'ssg') + "'>" + oSsgThis.sig + "</a></span>" +
            "<span class='pull-right clickable dct-hide' >" +
            "<a class='nostyle dct-blinded' onclick='ru.dct.dct_hiderow(this);' title='Hide this row'>" +
            "<span class='glyphicon glyphicon-minus' ></span></a></span></td>");
          // Keep track of data for getdata()
          datarow.push({ txt: oSsgThis.sig, siglist: siglist });

          if (bShowPivot) {
            html_row.push("<td class='fixed-side fixed-col1' data-toggle='tooltip' data-tooltip='dct-hover' align='center'" +
              " title='" + private_methods.dct_tooltip(oSsgThis, 'srm') + "' >" +
              oSsgThis.order + "<span class='hidden dct-author'>" + private_methods.dct_author(oSsgThis) + "</span></td>");
            // Keep track of data for getdata()
            datarow.push({ txt: oSsgThis.order.toString(), author: private_methods.dct_author(oSsgThis, true) });
          } else {
            html_row.push("<td class='fixed-side fixed-col1'>&nbsp;</td>");
            // Keep track of data for getdata()
            datarow.push({txt: ""});
          }
          ssg = oSsgThis.super;
          for (i = 0; i < ssglists.length; i++) {
            // Skip the pivot_col
            if (i !== pivot_col) {
              // Get this setlist
              ssglist = ssglists[i]['ssglist'];
              // Check if this one is not excluded
              if (lst_exclude.indexOf(ssglists[i].title.order) < 0) {
                // May include this one
                order = -1;
                // Look for this particular ssg within this list
                for (j = 0; j < ssglist.length; j++) {
                  oSsgItem = ssglist[j];
                  if (oSsgItem.super === ssg) {
                    // FOund one!
                    bFound = true;
                    order = oSsgItem.order;
                    break;
                  }
                }
                sClass = (i == 0) ? " class='fixed-side fixed-col1'" : "";
                if (order >= 0) {
                  html_row.push("<td" + sClass + " data-toggle='tooltip' data-tooltip='dct-hover' align='center'" +
                    " title='" + private_methods.dct_tooltip(oSsgItem, 'srm') + "'  >" +
                    order + "<span class='hidden dct-author'>" + private_methods.dct_author(oSsgItem) + "</span></td>");
                  // Keep track of data for getdata()
                  datarow.push({ txt: order.toString(), author: private_methods.dct_author(oSsgItem, true) });
                } else {
                  html_row.push("<td" + sClass + "></td>");
                  // Keep track of data for getdata()
                  datarow.push({ txt: "" });
                }
              }
            }
          }

          // Keep track of data for getdata()
          loc_dctdata.push({match: bFound, row: datarow });

          // Finish this row
          html_row.push("</tr>");
          // Return whether we found anything or not
          oBack['result'] = bFound;
          oBack['html'] = html_row.join("");
          return oBack;
        } catch (ex) {
          private_methods.errMsg("dct_row_combine", ex);
          // We didn't find anything
          oBack['error'] = true;
          oBack['msg'] = ex.message;
          return oBack;
        }
      },

      dct_saveshow: function() {
        $(".dct-view .dct-save-options").removeClass("hidden");
      },

      /** 
       *  dct_show - Show one DCT on the default location
       */
      dct_show: function (ssglists, params) {
        var elDctView = null,
            elDctShow = null,
            elDctWait = null,
            elDctTools = null,
            oTitle = null,
            oHeader = null,
            sTop = "",
            sMiddle = "",
            sMain = "",
            sUrl = "",
            sClass = "",
            iSize = 0,
            pivot = null,
            dealt_with = [],    // List of SSGs that have appeared in a row
            remainder = [],     // List with remainder
            lst_order = [],     // Which to include, in which order (if manually set)
            lst_exclude = [],   // Which to exclude (in any mode)
            ssglists_new = [],
            ssglist = null,
            oSsgItem = null,
            oSsgPivot = null,
            oCombi = null,
            bFound = false,
            marginleft = 0,
            order = 0,
            unique_matches = 0,
            oMatchSet = null,
            ssg = 0,
            row = 0,
            a_title = "",
            b_title = "",
            order = 0,
            i = 0,
            j = 0,
            rowcolor = "",
            col0 = {},
            col1 = {},
            pivot_col = 0,
            pivot_idx = 0,
            lHiddenRows = [],
            rowIndex = -1,
            order_key = "",
            view_mode = "all",        // May have values: 'all', 'match', 'expand'
            default_viewmode = "match",
            col_mode = "match_decr",  // May have values: 'match_decr', 'match_incr', 'alpha', 'chrono'
            datarow = [],
            html_row = [],
            html = [];

        try {
          // Parameter??
          if (params === undefined) {
            pivot_idx = 0;
          } else {
            // Get the pivot row
            if ("pivot_col" in params) { pivot_col = params['pivot_col'];}
            if ("view_mode" in params) { view_mode = params['view_mode'];}
            if ("col_mode" in params) { col_mode = params['col_mode']; }
            if ("lst_order" in params) { lst_order = params['lst_order']; }
            if ("lst_exclude" in params) { lst_exclude = params['lst_exclude']; }
            if ("hidden_rows" in params) { lHiddenRows = params['hidden_rows']; }
            if (col_mode === "custom") {
              // $("input[name='colorder']").prop("checked", false);
              $("#colmode option").prop("disabled", false);
              $("#colmode option[value='custom']").prop("selected", true);
            }
            // Adapt columns if pivot_col is different
            if (pivot_col >= 0) {
              // The [pivot_col] is the 'title.order' value - Check which index it is
              pivot_idx = -1;
              for (i = 0; i < ssglists.length; i++) {
                if (ssglists[i].title.order === pivot_col) {
                  pivot_idx = i;
                  break;
                }
              }
              ssglists_new.push(ssglists[pivot_idx]);
              for (i = 0; i < ssglists.length; i++) {
                if (i !== pivot_idx) {
                  ssglists_new.push(ssglists[i]);
                }
              }
              ssglists = ssglists_new;
              loc_ssglists = ssglists_new;

              // THe pivot_idx has now changed to column zero!
              pivot_idx = 0;
            }
          }

          // If we are going to view all, then make sure the hidden rows disappear
          if (view_mode === "all" && lHiddenRows.length > 0) {
            lHiddenRows = [];
          }

          // Make sure we save the parameters
          loc_params = {
            "pivot_col": pivot_col, "view_mode": view_mode, "col_mode": col_mode,
            "lst_order": lst_order, "lst_exclude": lst_exclude, "hidden_rows": lHiddenRows
          };

          // For further processing we need to have the actual 'order' value for the pivot column
          order_key = ssglists[pivot_idx]['title']['order'].toString();

          // Find out where the DCT should come
          elDctView = $(".dct-view").first();
          elDctShow = $(elDctView).find(".dct-show").first();
          elDctWait = $(elDctView).find(".dct-wait").first();
          elDctTools = $(elDctView).find(".dct-tools").first();

          // Clear the show part
          $(elDctShow).html();
          $(elDctTools).addClass("hidden");
          // Show the waiting part
          if ($(elDctWait).hasClass("hidden")) {
            $(elDctWait).removeClass("hidden");
          }

          // Sort the ssglists (the columns) according to what the user indicated
          for (i = 0; i < ssglists.length; i++) {
            ssglists[i]['title']['pivot'] = (i === pivot_idx) ? 0 : 1;
            // And set the right 'matches' value with respect to pivot_col
            oMatchSet = ssglists[i]['title']['matchset'];
            if (order_key in oMatchSet) {
              ssglists[i]['title']['matches'] = oMatchSet[order_key];
            }
          }
          ssglists.sort(function (a, b) {
            var retval = 0;

            // The pivot column should come first
            retval = a.title.pivot - b.title.pivot;

            // But if the pivot columns are equal (both are 1), then use a different measure
            if (retval == 0) {
              switch (col_mode) {
                case "rset":
                  // Follow the [order] definition
                  retval = (a.title.order > b.title.order) ? 1 : -1;
                  break;
                case "match_decr":
                  // First level: matches
                  if (a.title.matches < b.title.matches) {
                    retval = 1;
                  } else if (a.title.matches > b.title.matches) {
                    retval = -1;
                  } else {
                    // They are equal: check for order
                    retval = (a.title.order > b.title.order) ? 1 : -1;
                  }
                  break;
                case "match_incr":
                  // First level: matches
                  if (a.title.matches > b.title.matches) {
                    retval = 1;
                  } else if (a.title.matches < b.title.matches) {
                    retval = -1;
                  } else {
                    // They are equal: check for order
                    retval = (a.title.order > b.title.order) ? 1 : -1;
                  }
                  break;
                case "alpha":
                  // NOTE: this needs emending to facilitate: City > Library > shelfmark
                  if (a.title.top === "hc" || a.title.top === "pd") {
                    a_title = a.title.main;
                  } else {
                    a_title = a.title.top + "_" + a.title.middle + "_" + a.title.main;
                  }
                  if (b.title.top === "hc" || b.title.top === "pd") {
                    b_title = b.title.main;
                  } else {
                    b_title = b.title.top + "_" + b.title.middle + "_" + b.title.main;
                  }
                  retval = (a_title > b_title) ? 1 : -1;
                  break;
                case "custom":
                  retval = (lst_order.indexOf(a.title.order) > lst_order.indexOf(b.title.order)) ? 1 : -1;
                  break;
              }

            }

            /*
            // DEBUGGING: what is happening?
            console.log("ssglists a=[" + a.title.main + "].p" + a.title.pivot + ".m" + a.title.matches +
              " b=[" + b.title.main + "].p" + b.title.pivot + ".m" + b.title.matches +
              " --> " + retval);*/

            return retval;
          });

          // Walk the data for this DCT and construct the html
          html.push("<div class='table-scroll'><div class='table-wrap' id='dct_current_view'><table class='dct-view'>");
          // Construct the header
          html.push("<thead><tr><th class='fixed-side fixed-col0' order='0'>Gryson/Clavis</th>");
          datarow = [];
          loc_dctdata = [];
          datarow.push({ txt: "Gryson/Clavis" });
          for (i = 0; i < ssglists.length; i++) {
            // Get the title object
            oTitle = ssglists[i]['title'];
            // And get the order
            order = oTitle.order;
            // Should this one be included?
            if (lst_exclude.indexOf(order) < 0) {
              // This may be included
              sTop = "&nbsp;"; sMiddle = "&nbsp;"; sMain = "&nbsp;"; iSize = 0;
              if ('top' in oTitle) { sTop = oTitle['top']; if (sTop === "") sTop = "ms"; }
              if ('middle' in oTitle) { sMiddle = oTitle['middle']; }
              if ('main' in oTitle) { sMain = oTitle['main']; }
              if ('size' in oTitle) { iSize = oTitle['size']; }
              if ('url' in oTitle) { sUrl = oTitle['url']; }
              if ('unique_matches' in ssglists[i]) { unique_matches = ssglists[i]['unique_matches']; }

              // Keep track of the data for retrieval
              oHeader = {
                url: oTitle.url, top: oTitle.top, middle: oTitle.middle, main: oTitle.main,
                yearstart: oTitle.yearstart, yearfinish: oTitle.yearfinish, size: oTitle.size
              };
              datarow.push({ header: oHeader });

              // Show it
              if (i === 0) {
                sClass = "class='fixed-side fixed-col1'";
              } else {
                sClass = "class='draggable' draggable='true' " +
                  "ondragstart='ru.dct.dct_drag(event);' " +
                  "ondragend='ru.dct.dct_dragend(event);' " +
                  "ondragover='ru.dct.dct_dragenter(event);'";
              }
              html.push("<th " + sClass + " order='" + order.toString() + "'>");
              // Top 
              html.push("<div class='shelf-city' onclick='ru.dct.dct_pivot(" + order +
                ")' title='Click to make this the PIVOT&#10;&#13; (it would have " + unique_matches + " unique match[es])'>" + sTop + "</div>");
              // Middle
              html.push("<div class='shelf-library'>" + sMiddle + "</div>");
              // Main
              if (sUrl === "") {
                html.push("<div class='shelf-idno'>" + sMain + "</div>");
              } else {
                html.push("<div class='shelf-idno clickable'><a class='nostyle' href='" + sUrl + "'>" + sMain + "</a></div>");
              }
              // Size
              html.push("<div class='shelf-size'>" + iSize + "</div>");
              html.push("</th>");
            }

          }
          html.push("</tr></thead>");

          // Keep track of the data for getdata()
          loc_dctdata.push({ match: true, row: datarow });
          datarow = [];

          // Construct the body
          html.push("<tbody>");
          // Get the pivot: ssglist zero
          pivot = ssglists[pivot_idx]['ssglist'];
          rowcolor = "";
          // Walk the rows of the pivot
          for (row = 0; row < pivot.length; row++) {
            // Get details of this SSG
            oSsgPivot = pivot[row];
            // Get this SSG id
            ssg = oSsgPivot.super;
            // Mark it as dealt with 
            dealt_with.push(ssg);

            // Walk through all the other lists, finding this SSG
            oCombi = private_methods.dct_row_combine(ssglists, pivot_idx, oSsgPivot, rowcolor, true, lst_exclude);
            if (!oCombi.error) {
              // This action depends on the view mode
              switch (view_mode) {
                case "all":
                  // Always show the row
                  html.push(oCombi.html);
                  break;
                case "match":
                  // Found anything?
                  if (oCombi.result) {
                    // Add this row to the output
                    html.push(oCombi.html);
                  }
                  break;
              }
            }

          }

          // Depending on view mode: walk all other lists or not
          switch (view_mode) {
            case "all":
              // Get a list of remaining *objects* to be dealt with
              remainder = private_methods.dct_remaining_ssgs(ssglists, pivot_idx, dealt_with);
              // Walk all these objects
              for(row=0;row<remainder.length;row++) {
                // Get this object
                oSsgPivot = remainder[row];

                // Walk through all the other lists, finding this SSG
                oCombi = private_methods.dct_row_combine(ssglists, pivot_idx, oSsgPivot, rowcolor, false, lst_exclude);

                if (!oCombi.error) {
                  // Always show the row
                  html.push(oCombi.html);
                }
              }
              break;
          }

          html.push("</tbody>");

          // Finish the table
          html.push("</div></div></table>");

          // Add the created DCT
          $(elDctShow).html(html.join("\n"));
          // Walk all the rows of <tbody>
          if (lHiddenRows.length > 0) {
            $(elDctShow).find("table tbody tr").each(function (idx, el) {
              if (lHiddenRows.indexOf(idx) >= 0) {
                $(el).addClass("hidden dct_hidden");
              }
            });
            // Make sure we show the 'expand' button
            $(".dct-expand").removeClass("hidden");
          } else {
            // Make sure the expand button is hidden
            $(".dct-expand").addClass("hidden");
          }

          // Perform row-coloring
          $(elDctShow).find("table tbody tr").each(function (idx, el) {
            // Row coloring, stage 1
            var rowcolor = (idx % 2 === 0) ? "dct-even" : "dct-odd";

            $(el).addClass(rowcolor);
          });
          // Attach row-highlighting handler
          $(elDctShow.find("table tbody tr td.fixed-col1")).unbind("click").on("click", function (evt) {
            private_methods.dct_highlight(this);
          });

          // initialize tooltipping:
          private_methods.dct_showtooltip_init();

          // Now show it
          $(elDctTools).removeClass("hidden");

          // Hide the waiting part
          $(elDctWait).addClass("hidden");

          // Calculate the correct "left" values for the first column
          $(elDctShow).find("table th.fixed-side.fixed-col0").each(function (idx, el) {
            var iLeft = 0, sWidth = "", oCss = {};

            // Get the current left position
            iLeft = Math.max(0, el.offsetLeft);
            sWidth = $(el).css("width");
            sWidth = el.offsetWidth + 30;
            col0 = { "width": sWidth, "min-width": sWidth, "max-width": sWidth, "left": iLeft };

          });

          // Calculate the correct "left" values for the second column
          $(elDctShow).find("table th.fixed-side.fixed-col1").each(function (idx, el) {
            var iLeft = 0, sWidth = "", oCss = {};

            // Get the current left position
            iLeft = Math.max(0, el.offsetLeft);
            sWidth = $(el).css("width");
            col1 = { "width": sWidth, "min-width": sWidth, "max-width": sWidth, "left": iLeft };

          });

          // Now fix this throughout the table
          $(elDctShow.find("table .fixed-col0")).css(col0);
          $(elDctShow.find("table .fixed-col1")).css(col1);

        } catch (ex) {
          private_methods.errMsg("dct_show", ex);
        }
      },

      /** 
       *  dct_showhidealt - Show or hide the [dct-alt]
       */
      dct_showhidealt: function () {
        try {
          if ($(".dct-showhidealt").first().hasClass("active")) {
            // SHow the alt text
            $(".dct-alt").removeClass("hidden");
          } else {
            // Hide the alt text
            $(".dct-alt").addClass("hidden");
          }
        } catch (ex) {
          private_methods.errMsg("dct_showhidealt", ex);
        }
      },

      /** 
       *  dct_showtooltip_init - Initialize tooltip processing
       */
      dct_showtooltip_init: function () {
        try {
          // initialize tooltipping: hover-type
          $('.dct-view td[data-toggle="tooltip"][data-tooltip="dct-hover"], .dct-view a[data-toggle="tooltip"][data-tooltip="dct-hover"]').tooltip({
            html: true,
            container: 'body',
            placement: 'bottom auto',
            animation: true,
            trigger: "hover",
            delay: 800,
            template: '<div class="tooltip dct"><div class="tooltip-arrow"></div><div class="tooltip-inner"></div></div>'
          });

          // What to do when a tooltip has been shown
          $('.dct-view td[data-toggle="tooltip"][data-tooltip="dct-hover"], .dct-view a[data-toggle="tooltip"][data-tooltip="dct-hover"]').on('shown.bs.tooltip', function () {
            private_methods.dct_showhidealt();
          });


        } catch (ex) {
          private_methods.errMsg("dct_showtooltip_init", ex);
        }
      },

      /** 
       *  dct_tooltip - Calculate the tooltip for this one
       *
       *  type can be: 'ssg' or 'srm'
       */
      dct_tooltip: function (oSsgItem, type) {
        var html = [], i = 0, label = "", key = "",
            itemtype = "",
            sValue = "",
            phase = 1;

        try {
          html.push("<table><tbody>");

          // Get the item type
          if ("type" in oSsgItem) {
            itemtype = oSsgItem['type'];
            if ((itemtype === "hc" || itemtype === "pd") && type === "srm") {
              // It doesn't make sense to show [srm] for a collection, since that doesn't exist
              type = "ssg";
            }
          }

          // Action depends on the type
          switch (type) {
            case "ssg": // Information for the leftmost cell in the DCT
              for (i = 0; i < loc_dctTooltip.length; i++) {
                label = loc_dctTooltip[i]["label"];
                key = loc_dctTooltip[i]["key"];
                if (key in oSsgItem) {
                  sValue = oSsgItem[key];
                  if (sValue === null) { sValue = "-";}
                  html.push("<tr><td class='tdnowrap' valign='top'>" + label + ":</td><td valign='top'>" + sValue + "</td></tr>");
                }
              }
              switch (itemtype) {
                case "hc":
                case "pd":
                  for (i = 0; i < loc_dctTooltipCollection.length; i++) {
                    label = loc_dctTooltipCollection[i]["label"];
                    key = loc_dctTooltipCollection[i]["key"];
                    if (key in oSsgItem) {
                      sValue = oSsgItem[key];
                      if (sValue === null) { sValue = "-"; }
                      html.push("<tr><td class='tdnowrap' valign='top'>" + label + ":</td><td valign='top'>" + sValue + "</td></tr>");
                    }
                  }
                  break;
              }
              break;
            case "srm": // Information for the regular cells in the DCT
              // Add the sermon-items, but hide them initially
              for (i = 0; i < loc_dctTooltipAdditional.length; i++) {
                label = loc_dctTooltipAdditional[i]["label"];
                key = loc_dctTooltipAdditional[i]["key"];
                if (key in oSsgItem) {
                  sValue = oSsgItem[key];
                  if (sValue === null) { sValue = "-"; }
                  html.push("<tr><td class='tdnowrap' valign='top'>" + label + ":</td><td valign='top'>" + sValue + "</td></tr>");
                }
              }
              break;
          }

          html.push("</tbody></table>");

          // Combine the html
          return html.join("").replaceAll("'", "\"");
        } catch (ex) {
          private_methods.errMsg("dct_tooltip", ex);
        }
      },

      /** 
       *  errClear - clear the error <div>
       */
      errClear: function () {
        $("#" + loc_divErr).html("");
      },

      /** 
       *  errMsg - show error message in <div> loc_divErr
       */
      errMsg: function (sMsg, ex) {
        var sHtml = "Error in [" + sMsg + "]<br>";
        if (ex !== undefined && ex !== null) {
          sHtml = sHtml + ex.message;
        }
        $("#" + loc_divErr).html(sHtml);
      },

      /** 
       *  getStyleVal - needed for resizableGrid
       */
      getStyleVal: function (elm, css) {
        return (window.getComputedStyle(elm, null).getPropertyValue(css))
      },

      /** 
       *  paddingDiff - needed for resizableGrid
       */
      paddingDiff: function (col) {
        if (private_methods.getStyleVal(col, 'box-sizing') == 'border-box') {
          return 0;
        }

        var padLeft = private_methods.getStyleVal(col, 'padding-left');
        var padRight = private_methods.getStyleVal(col, 'padding-right');
        return (parseInt(padLeft) + parseInt(padRight));
      },

      /**
       * prepend_styles
       *    Get the html in sDiv, but prepend styles that are used in it
       * 
       * @param {el} HTML dom element
       * @returns {string}
       */
      prepend_styles: function (sDiv, sType) {
        var lData = [],
            el = null,
            i, j,
            sheets = document.styleSheets,
            used = "",
            elems = null,
            tData = [],
            rules = null,
            rule = null,
            s = null,
            sSvg = "",
            defs = null;

        try {
          // Get the correct element
          if (sType === "svg") { sSvg = " svg"; }
          el = $(sDiv + sSvg).first().get(0);
          // Get all the styles used 
          for (i = 0; i < sheets.length; i++) {
            try {
              rules = sheets[i].cssRules;
            } catch (ex) {
              // Just continue
            }
            for (j = 0; j < rules.length; j++) {
              rule = rules[j];
              if (typeof (rule.style) !== "undefined") {
                elems = el.querySelectorAll(rule.selectorText);
                if (elems.length > 0) {
                  used += rule.selectorText + " { " + rule.style.cssText + " }\n";
                }
              }
            }
          }

          // Get the styles
          s = document.createElement('style');
          s.setAttribute('type', 'text/css');
          switch (sType) {
            case "html":
              s.innerHTML = used;

              // Get the table
              tData.push("<table class=\"func-view\">");
              tData.push($(el).find("thead").first().get(0).outerHTML);
              tData.push("<tbody>");
              $(el).find("tr").each(function (idx) {
                if (idx > 0 && !$(this).hasClass("hidden")) {
                  tData.push(this.outerHTML);
                }
              });
              tData.push("</tbody></table>");

              // Turn into a good HTML
              lData.push("<html><head>");
              lData.push(s.outerHTML);
              lData.push("</head><body>");
              // lData.push(el.outerHTML);
              lData.push(tData.join("\n"));

              lData.push("</body></html>");
              break;
            case "svg":
              s.innerHTML = "<![CDATA[\n" + used + "\n]]>";

              defs = document.createElement('defs');
              defs.appendChild(s);
              el.insertBefore(defs, el.firstChild);

              el.setAttribute("version", "1.1");
              el.setAttribute("xmlns", "http://www.w3.org/2000/svg");
              el.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
              lData.push("<?xml version=\"1.0\" standalone=\"no\"?>");
              lData.push("<!DOCTYPE svg PUBLIC \"-//W3C//DTD SVG 1.1//EN\" \"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd\" >");
              lData.push(el.outerHTML);
              break;
          }

          return lData.join("\n");
        } catch (ex) {
          private_methods.showError("prepend_styles", ex);
          return "";
        }
      },

      /**
       * resizableGrid
       *    Set the table to have resizable columns
       *    
       *    Idea: https://www.brainbell.com/javascript/making-resizable-table-js.html
       *
       */
      resizableGrid: function (elTable) {
        var row = null,
            cols = null,
            div = null,
            eltarget = null,
            tableHeight = 0;

        try {
          // Get the row and the columns
          row = $(elTable).find("tr").first();
          cols = $(row).children();

          // Sanity:
          if (!cols) return;

          // Get the table height and the table width
          tableHeight = elTable.offsetHeight;
          // Add a div with a listener
          for (var i = 0; i < cols.length; i++) {
            div = private_methods.createDiv(tableHeight, i);
            cols[i].appendChild(div);
            cols[i].style.position = 'relative';
            cols[i].style.cursor = 'pointer';
            private_methods.setListeners(div);
            // Need to add an event, but where?
            if ($(cols[i]).find("span.sortable").length > 0) {
              // We need to be able to sort
              eltarget = $(cols[i]).find("span.sortable").find("span").last();
              $(eltarget)[0].addEventListener('click', private_methods.toggle_column);
            } else {
              // Add a click event listener to the <th> column
              cols[i].addEventListener('click', private_methods.toggle_column);
            }
          }

        } catch (ex) {
          private_methods.errMsg("resizableGrid", ex);
        }
      },

      /** 
       *  setListeners - needed for resizableGrid
       */
      setListeners: function (div) {
        var pageX,
            curCol,
            nxtCol,
            colidx,
            rows,
            curColWidth,
            nxtColWidth;

        // What happens when user clicks on a mouse
        div.addEventListener('mousedown', function (e) {
          curCol = e.target.parentElement;    // The column where the cursor is
          nxtCol = curCol.nextElementSibling; // The next column
          pageX = e.pageX; 
          colidx = parseInt($(e.target).attr("colidx"), 10);
 
          var padding = private_methods.paddingDiff(curCol);
 
          curColWidth = curCol.offsetWidth - padding;
          if (nxtCol)
            nxtColWidth = nxtCol.offsetWidth - padding;

          // Set what the rows are
          rows = $(e.target).closest("table").find("tbody tr");
        });

        // What happens when user hovers over
        div.addEventListener('mouseover', function (e) {
          e.target.style.borderRight = '2px solid #0000ff';
        })

        // The mouse goes out of the area of attention
        div.addEventListener('mouseout', function (e) {
          e.target.style.borderRight = '';
        })

        // User is moving the mouse
        document.addEventListener('mousemove', function (e) {

          if (curCol) {
            var diffX = e.pageX - pageX;
 
            if (nxtCol) {
              nxtCol.style.width = (nxtColWidth - (diffX)) + 'px';
              nxtCol.style.maxWidth = (nxtColWidth - (diffX)) + 'px';
            }

            curCol.style.width = (curColWidth + diffX)+'px';
            curCol.style.maxWidth = (curColWidth + diffX) + 'px';

            // Make sure the width of all table columns at this position is set
            
            $(rows).each(function (idx, el) {
              var td = $(el).find("td")[colidx];
              td.style.maxWidth = curCol.style.maxWidth;
              td.style.width = curCol.style.maxWidth;
            });
          }
        });

        // User does mouse 'up'
        document.addEventListener('mouseup', function (e) {
          curCol = undefined;
          nxtCol = undefined;
          pageX = undefined;
          nxtColWidth = undefined;
          curColWidth = undefined
        });
      },

      /** 
       *  sortshowDo - perform sorting on this <th> column
       */
      sortshowDo: function (el) {
        var elTable = $(el).closest("table"),
            elTbody = $(elTable).find("tbody").first(),
            elTh = $(el).closest("th"),
            elSortable = $(el).closest(".sortable"),
            rows = null,
            sDirection = "desc",
            sSortType = "text",   // Either text or integer
            elDiv = null,
            colidx = -1;

        try {
          // Find out which direction is needed
          if ($(el).hasClass("fa-sort-down")) sDirection = "asc";
          if ($(elSortable).hasClass("integer")) sSortType = "integer";
          // restore direction everywhere in headers
          $(el).closest("tr").find(".fa.sortshow").each(function (idx, elSort) {
            $(elSort).removeClass("fa-sort-down");
            $(elSort).removeClass("fa-sort-up");
            $(elSort).addClass("fa-sort");
          });
          switch (sDirection) {
            case "asc":
              $(el).removeClass("fa-sort");
              $(el).addClass("fa-sort-up");
              break;
            case "desc":
              $(el).removeClass("fa-sort");
              $(el).addClass("fa-sort-down");
              break;
          }
          // Get the colidx
          elDiv = $(elTh).find("div[colidx]").first();
          if ($(elDiv).length > 0) {
            // Get the column index 0-n
            colidx = parseInt($(elDiv).attr("colidx"), 10);

            private_methods.sortTable(elTable, colidx, sDirection, sSortType);

            // Show that changes can/need to be saved
            $(elTable).closest("div").find(".related-save").removeClass("hidden");

          }
        } catch (ex) {
          private_methods.errMsg("sortshowDo", ex);
        }
      },

      /** 
       *  sortTable - sort any table on any colum into any direction
       *              @sorttype is either 'text' or 'integer' (if defined)
       */
      sortTable: function (elTable, colidx, direction, sorttype) {
        var rows = $(elTable).find('tbody  tr').get();

        // Make sure to set sorttype to something
        if (sorttype === undefined) sorttype = "text";

        // The sorttype determines the sort function
        if (sorttype == "integer") {
          rows.sort(function (a, b) {
            var A = 0, B = 0, sA = "", sB = "";

            // Get the numerical values of A and B
            sA = $(a).children('td').eq(colidx).text().match(/\d+/);
            sB = $(b).children('td').eq(colidx).text().match(/\d+/);
            if (sA !== "") A = parseInt(sA.join(''), 10);
            if (sB !== "") B = parseInt(sB.join(''), 10);

            switch (direction) {
              case "desc":
                if (A < B) { return -1; } else if (A > B) { return 1; } else return 0;
              case "asc":
                if (A < B) { return 1; } else if (A > B) { return -1; } else return 0;
            }

          });
          $.each(rows, function (index, row) {
            $(elTable).children('tbody').append(row);
          });
        } else {
          rows.sort(function (a, b) {
            var A = $(a).children('td').eq(colidx).text().toUpperCase();
            var B = $(b).children('td').eq(colidx).text().toUpperCase();

            switch (direction) {
              case "desc":
                if (A < B) { return -1; } else if (A > B) { return 1; } else return 0;
              case "asc":
                if (A < B) { return 1; } else if (A > B) { return -1; } else return 0;
            }

          });
          $.each(rows, function (index, row) {
            $(elTable).children('tbody').append(row);
          });
        }

      },

      /**
       * converts an svg string to base64 png using the domUrl
       * @param {string} svgText the svgtext
       * @param {number} [margin=0] the width of the border - the image size will be height+margin by width+margin
       * @param {string} [fill] optionally backgrund canvas fill
       * @return {Promise} a promise to the bas64 png image
       */
      svgToPng: function (svgText, options /*margin,fill */) {
        var margin, fill;

        // convert an svg text to png using the browser
        return new Promise(function (resolve, reject) {
          var match = null,
              height = 200,
              width = 200;

          try {
            // can use the domUrl function from the browser
            var domUrl = window.URL || window.webkitURL || window;
            if (!domUrl) {
              throw new Error("(browser doesnt support this)")
            }
        
            // figure out the height and width from svg text
            if (options.height) {
              height = options.height;
            } else {
              match = svgText.match(/height=\"(\d+)/m);
              height = match && match[1] ? parseInt(match[1], 10) : 200;
            }
            if (options.width) {
              width = options.width;
            } else {
              match = svgText.match(/width=\"(\d+)/m);
              width = match && match[1] ? parseInt(match[1], 10) : 200;
            }
            margin = margin || 0;
        
            // it needs a namespace
            if (!svgText.match(/xmlns=\"/mi)){
              svgText = svgText.replace ('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ') ;  
            }
        
            // create a canvas element to pass through
            var canvas = document.createElement("canvas");
            canvas.width = height+margin*2;
            canvas.height = width+margin*2;
            var ctx = canvas.getContext("2d");
        
        
            // make a blob from the svg
            var svg = new Blob([svgText], {
              type: "image/svg+xml;charset=utf-8"
            });
        
            // create a dom object for that image
            var url = domUrl.createObjectURL(svg);
        
            // create a new image to hold it the converted type
            var img = new Image;
        
            // when the image is loaded we can get it as base64 url
            img.onload = function() {
              // draw it to the canvas
              ctx.drawImage(this, margin, margin);
          
              // if it needs some styling, we need a new canvas
              if (fill) {
                var styled = document.createElement("canvas");
                styled.width = canvas.width;
                styled.height = canvas.height;
                var styledCtx = styled.getContext("2d");
                styledCtx.save();
                styledCtx.fillStyle = fill;   
                styledCtx.fillRect(0,0,canvas.width,canvas.height);
                styledCtx.strokeRect(0,0,canvas.width,canvas.height);
                styledCtx.restore();
                styledCtx.drawImage (canvas, 0,0);
                canvas = styled;
              }
              // we don't need the original any more
              domUrl.revokeObjectURL(url);
              // now we can resolve the promise, passing the base64 url
              resolve(canvas.toDataURL());
            };
        
            // load the image
            img.src = url;
        
          } catch (err) {
            reject('failed to convert svg to png ' + err);
          }
        });
      },

      /** 
       *  toggle_column - show or hide column
       */
      toggle_column: function (e) {
        var th = $(e.target).closest("th"),
            table = $(th).closest("table"),
            bSkip = false,
            tableWidth = 0,
            colid = parseInt($(th).find("div").first().attr("colidx"), 10);

        // Calculate values
        tableWidth = table[0].offsetWidth;
        // Walk all rows in the table
        $(table).find("tr").each(function (idx, el) {
          var td = null,
              width = 0,
              maxWidth = 0;

          if (idx === 0) {
            td = $(el).find("th")[colid];
            if (td.style.width.indexOf("100%") >= 0) {
              bSkip = true;
            }
          } else if (!bSkip) {
            // Get this td
            td = $(el).find("td")[colid];

            // See which way the toggling goes: check if max-width equals 10px
            if (td.style.maxWidth === "10px") {
              // Expand: remove max and min width
              width = td.style.width;
              maxWidth = td.style.maxWidth;
              // Now reset the current styling
              td.style = "";
              // Check how wide we become
              if (table[0].offsetWidth > tableWidth) {
                // Revert: we are not able to expand further
                td.style.width = width;
                td.style.maxWidth = maxWidth;
              }
            } else {
              // Shrink: set max and min width
              td.style.maxWidth = "10px";
              td.style.minWidth = "10px";
            }
          }
        });
      },

      /** 
       *  waitInit - initialize waiting
       */
      waitInit: function (el) {
        var elWaith = null;

        try {
          // Right now no initialization is defined
          return elWait;
        } catch (ex) {
          private_methods.errMsg("waitInit", ex);
        }
      },

      /** 
       *  waitStart - Start waiting by removing 'hidden' from the DOM point
       */
      waitStart: function (el) {
        if (el !== null) {
          $(el).removeClass("hidden");
        }
      },

      /** 
       *  waitStop - Stop waiting by adding 'hidden' to the DOM point
       */
      waitStop: function (el) {
        if (el !== null) {
          $(el).addClass("hidden");
        }
      }
    }
    // Public methods
    return {

      /**
       * dct_additional
       *    Show or hide additional information on hovering
       *
       */
      dct_additional: function (elStart) {
        var bPressed = false;

        try {
          //TOggle it
          if ($(elStart).hasClass("active")) {
            $(elStart).removeClass("active");
            $(elStart).removeAttr("aria-pressed");
          } else {
            $(elStart).addClass("active");
            $(elStart).attr("aria-pressed", true);
          }
          // Check what now
          bPressed = $(elStart).hasClass("active");
          if (bPressed !== undefined && bPressed) {
            // Show the additional information
            $(".dct-view .dct-alt").removeClass("hidden");
          } else {
            // Hide the additional information
            $(".dct-view .dct-alt").addClass("hidden");
          }

        } catch (ex) {
          private_methods.errMsg("dct_additional", ex);
        }
      },

      /**
       * dct_addsrc
       *    Actually add this source list
       *
       */
      dct_addsrc: function (elStart) {
        var sType = "",
            sId = "",
            ajaxurl = "",
            frm = null,
            data = null;

        try {
          // Check which one is visible
          if (!$(".source-list.source-manu").hasClass("hidden")) {
            sType = "manu";
            sId = $("#id_sdef-manulist").val();
          } else if (!$(".source-list.source-coll").hasClass("hidden")) {
            sType = "coll";
            sId = $("#id_sdef-histlist").val();
          }
          // Process these values
          if (sType !== "" && sId !== "") {
            $("#addtype").val(sType);
            $("#addid").val(sId);
          }

          // Always:
          $(".source-list").addClass("hidden");

          // Do we have an url?
          ajaxurl = $(elStart).attr("ajaxurl");
          if (ajaxurl !== "" && ajaxurl !== undefined) {
            frm = $(elStart).closest("form").first();
            // Show waiting
            $(".waiting").removeClass("hidden");
            // Submit with this data
            $(frm).attr("action", ajaxurl);
            $(frm).submit();
          }

        } catch (ex) {
          private_methods.errMsg("dct_addsrc", ex);
        }
      },

      /**
       * dct_author
       *    Show or hide author information
       *
       */
      dct_author: function (elStart) {
        var bPressed = false;

        try {
          //TOggle it
          if ($(elStart).hasClass("active")) {
            $(elStart).removeClass("active");
            $(elStart).removeAttr("aria-pressed");
          } else {
            $(elStart).addClass("active");
            $(elStart).attr("aria-pressed", true);
          }
          // Check what now
          bPressed = $(elStart).hasClass("active");
          if (bPressed !== undefined && bPressed) {
            // Show the additional information
            $(".dct-view .dct-author").removeClass("hidden");
          } else {
            // Hide the additional information
            $(".dct-view .dct-author").addClass("hidden");
          }

        } catch (ex) {
          private_methods.errMsg("dct_author", ex);
        }
      },

      /**
       * dct_cancel
       *    Cancel saving and return to the previously copied state
       *
       */
      dct_cancel: function (elStart) {
        var elRoot = null,
            elCopy = null,
            elOriginal = null;

        try {
          elRoot = $(elStart).closest(".dct-root");
          if (elRoot.length > 0) {
            elOriginal = $(elRoot).find(".dct-view").first();
            elCopy = $(elRoot).find(".dct-copy").first();
            if (elOriginal.length > 0 && elCopy.length > 0) {
              // Copy from copy to original
              $(elOriginal).html($(elCopy).html());

              // initialize tooltipping:
              private_methods.dct_showtooltip_init();

            }
          }
        } catch (ex) {
          private_methods.errMsg("dct_cancel", ex);
        }        
      },

      /**
       * dct_download
       *    Facilitate downloading a DCT
       *
       */
      dct_download: function (elStart) {
        try {
          switch ($(elStart).attr("downloadtype")) {
            case "json":
            case "xlsx":
              // Prepare a JSON to work from
              $("#downloaddata").val(private_methods.dct_getdata());
              break;
          }

          // Now make the actual call for the downloading
          ru.basic.post_download(elStart, {waitclass: "waiting"});
        } catch (ex) {
          private_methods.errMsg("dct_download", ex);
        }
      },

      /**
       * dct_drag
       *    Starting point of dragging. 
       *    The DOM object of the <th> is stored in [loc_columnTh]
       *
       */
      dct_drag: function (ev) {
        var row = "";
        try {
          // Check this out
          if ($(ev.target).parent().hasClass("shelf-idno")) {
            loc_columnTh = null;
            return;
          }
          loc_columnTh = null;
          loc_columnTh = ev.target;
        } catch (ex) {
          private_methods.errMsg("dct_drag", ex);
        }
      },

      /**
       * dct_dragenter
       *    Dragging one column over other columns
       *
       */
      dct_dragenter: function (ev) {
        var th_src = null,
            children = null;

        try {
          if (loc_columnTh === null) {
            // Leave immediately
            return;
          }
          // Prevend the default behaviour
          ev.preventDefault();

          // make sure the drag destination is up to date
          loc_dragDst = ev.target;

          // Get the column that is stored
          th_src = loc_columnTh;
          // We must be going over a TH with the right class
          if (ev.target.nodeName.toLowerCase() === "th" && $(ev.target).hasClass("draggable")) {

            // Get the <th> children in one array
            children = Array.from(ev.target.parentNode.children);
            // Check whether we are before or after the target
            if (children.indexOf(ev.target) > children.indexOf(th_src)) {
              // Target comes after
              ev.target.after(th_src);
            } else if (children.indexOf(ev.target) < children.indexOf(th_src)) {
              // Target comes before
              ev.target.before(th_src);
            }

            // Show that changes can/need to be saved
            // $(ev.target).closest("table").closest("div").find(".related-save").removeClass("hidden");

          }
        } catch (ex) {
          private_methods.errMsg("dct_dragenter", ex);
        }
      },

      /**
       * dct_dragend
       *    Dragging has finished: re-order
       *
       */
      dct_dragend: function (ev) {
        var th_src = null,
            lst_order = [],
            lst_exclude = [],
            order = 0,
            i = 0,
            children = null;

        try {
          // Prevend the default behaviour
          ev.preventDefault();

          // Is this deleting or what?
          if (loc_dragDst !== null && $(loc_dragDst).hasClass("delete")) {
            // Need to delete this node
            order = $(ev.target).attr("order");
            // Add this to the exclude list
            if ("lst_exclude" in loc_params) {
              lst_exclude = loc_params['lst_exclude'];
            }
            lst_exclude.push(parseInt(order, 10));
            loc_params['lst_exclude'] = lst_exclude;
          } else {
            // Get the current order of the columns
            children = Array.from(ev.target.parentNode.children);
            for (i = 0; i < children.length; i++) {
              order = parseInt($(children[i]).attr("order"), 10);
              if (order > 0) {
                lst_order.push(order);
              }
            }

            // Sort custom according to this order
            loc_params['col_mode'] = "custom";
            loc_params['lst_order'] = lst_order;

          }


          private_methods.dct_show(loc_ssglists, loc_params);

          // Make sure save buttons are shown
          private_methods.dct_saveshow();
        } catch (ex) {
          private_methods.errMsg("dct_dragend", ex);
        }
      },

      /**
       * dct_expand
       *    Expand all rows that were manually hidden
       *
       */
      dct_expand: function (elStart) {
        var elRow = null,
            lHiddenRows = [],
            iRow = -1;

        try {
          // Reset the hidden_rows storage
          loc_params['hidden_rows'] = [];

          // Un-hide the rows
          $(".dct-view tbody tr.dct_hidden").removeClass("hidden dct_hidden");

          // Now hide the 'Expand' button
          $(".dct-expand").addClass("hidden");

          // Make sure save buttons are shown - this implies that the current status can be saved
          private_methods.dct_saveshow();
        } catch (ex) {
          private_methods.errMsg("dct_expand", ex);
        }
      },

      /**
       * dct_hiderow
       *    Hide the row from view
       *
       */
      dct_hiderow: function (elStart) {
        var elRow = null,
            lHiddenRows = [],
            iRow = -1;

        try {
          // Get the row
          elRow = $(elStart).closest("tr");
          // Store the rowindex
          iRow = elRow.index();
          if ('hidden_rows' in loc_params) {
            lHiddenRows = loc_params['hidden_rows'];
          }
          lHiddenRows.push(iRow);
          loc_params['hidden_rows'] = lHiddenRows;

          // Hide it and give it a label for recognition
          $(elRow).addClass("hidden dct_hidden");

          // Now show the 'Expand' button
          $(".dct-expand").removeClass("hidden");

          // Make sure save buttons are shown - this implies that the current status can be saved
          private_methods.dct_saveshow();
        } catch (ex) {
          private_methods.errMsg("dct_hiderow", ex);
        }
      },

      /**
       * dct_pivot
       *    Take the indicated column as pivot for the DCT
       *
       * Note from issue #396:
       *    If there are multiple source-lists with the same number of matches, 
       *    the oldest (manuscript) source-list should be selected.
       *
       */
      dct_pivot: function (pivot_col) {
        var params,
            i = 0,
            unique_matches = -1,
            min_order = -1,
            min_year_finish = 3000,
            min_year_start = 3000,
            order = -1,
            default_colmode = "match_decr",
            year_finish = -1,
            year_start = -1,
            max_matches = -1;

        try {
          // Need to adapt the colmode
          $("#colmode option[value='" + default_colmode + "']").prop("selected", true);
          $("#colmode option[value='custom']").prop("disabled", true);
          loc_params['col_mode'] = default_colmode;
          // Take the local parameters
          params = loc_params;
          // Change the pivot column
          if (pivot_col < 0) {
            // Take the best matching column from loc_ssglists
            min_order = loc_ssglists.length + 2;
            for (i = 0; i < loc_ssglists.length; i++) {
              unique_matches = loc_ssglists[i]['unique_matches'];
              order = loc_ssglists[i]['title']['order'];
              year_start = loc_ssglists[i]['title']['year_start'];
              year_finish = loc_ssglists[i]['title']['year_finish'];
              if (unique_matches > max_matches ||
                  (unique_matches === max_matches && year_start < min_year_start ) ||
                  (unique_matches === max_matches && year_start === min_year_start && year_finish < min_year_finish) ||
                  (unique_matches === max_matches && year_start === min_year_start && year_finish === min_year_finish && order < min_order)) {
                max_matches = unique_matches;
                min_order = order;
                min_year_finish = year_finish;
                min_year_start = year_start;
                // pivot_col = loc_ssglists[i]['title']['order'];
                pivot_col = order;
              }
            }
          }
          params['pivot_col'] = pivot_col;
          // show this DCT
          private_methods.dct_show(loc_ssglists, params);

          // Make sure save buttons are shown
          private_methods.dct_saveshow();
        } catch (ex) {
          private_methods.errMsg("dct_pivot", ex);
        }
      },

      /**
       * dct_save
       *    Save changes to the DCT
       *
       */
      dct_save: function (el, elDctId, save_mode) {
        var frm = null,
            data = null,
            err = "#little_err_msg",
            targeturl = null,
            contents = null,
            ssglists = null,
            params = null;

        try {
          // Get the target URL
          targeturl = $(elDctId).attr("targeturl");

          // Get to the form
          frm = $(elDctId).closest("form");
          data = frm.serializeArray();

          // Add the parameters to the information
          data.push({ "name": "params", "value": JSON.stringify( loc_params) });
          data.push({ "name": "save_mode", "value": save_mode });

          //SHow we are waiting
          $(".dct-save-waiting").removeClass("hidden");

          // Try to delete: send a POST
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }
            }
          });
        } catch (ex) {
          private_methods.errMsg("dct_save", ex);
        }
      },

      /**
       * dct_source
       *    Show or hide a source list
       *
       */
      dct_source: function (elStart) {
        var sType = "";

        try {
          sType = $(elStart).attr("source");
          switch (sType) {
            case "manu":
              $(".source-list").addClass("hidden");
              $(".source-manu").removeClass("hidden");
              break;
            case "coll":
              $(".source-list").addClass("hidden");
              $(".source-coll").removeClass("hidden");
              break;
            default:
              $(".source-list").addClass("hidden");
              break;
          }
        } catch (ex) {
          private_methods.errMsg("dct_source", ex);
        }
      },

      /**
       * do_savedsearch
       *    Add or remove saved item request
       *
       */
      do_savedsearch: function (elStart, sAction) {
        var frm = null,
            targeturl = "",
            action = "",
            searchid = "#savedsearchdetails",
            resultid = "#savedsearchresult",
            data = null;

        try {
          // Get to the form
          frm = $(elStart).closest("form");
          // Get the data
          data = $(frm).serializeArray();

          // Get the URL
          targeturl = $(elStart).attr("targeturl");

          // Show the waiting symbol
          $(searchid).removeClass("in");
          $(searchid).addClass("collapse");
          $(resultid).html(loc_sWaiting);
          $(resultid).removeClass("hidden");

          // Double check
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  action = response['action'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else if (action !== undefined && action !== "") {
                    switch (action) {
                      case "deleted":
                      case "removed":
                        //// $(elStart).css("color", "gray");
                        //$(elStart).removeClass("sitem-button-selected");
                        //$(elStart).addClass("sitem-button");
                        //$(elStart).html('<span class="glyphicon glyphicon-star-empty"></span>');
                        //$(elStart).attr("title", "Add to your saved items");
                        // Change the sitem action to be taken
                        $("#id_sitemaction").val("add");
                        break;
                      case "script":
                        // Provide warning that user attempted to enter a script name
                        $(resultid).html("<span style='color: red'>SCRIPT??</span>");
                        $(searchid).removeClass("collapse");
                        $(searchid).addClass("in");
                        setTimeout(function () {
                          $(resultid).addClass("hidden");
                        }, 8000);
                        break;
                      case "empty":
                        // Give warning that name is empty
                        $(resultid).html("<span style='color: red'>NAME??</span>");
                        $(searchid).removeClass("collapse");
                        $(searchid).addClass("in");
                        setTimeout(function () {
                          $(resultid).addClass("hidden");
                        }, 8000);
                        break;
                      case "added":
                        $(resultid).html("<span style='color: red'>saved</span>");
                        setTimeout(function () {
                          $(resultid).addClass("hidden");
                        }, 3000);
                        break;
                    }
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });


        } catch (ex) {
          private_methods.errMsg("do_savedsearch", ex);
        }
      },

      /**
       * do_saveditem
       *    Add or remove saved item request
       *
       */
      do_saveditem: function (elStart, sAction) {
        var frm = null,
            targeturl = "",
            action = "",
            data = null;

        try {
          // Get to the form
          frm = $(elStart).closest(".sitem").attr("targetid");
          // Get the data
          data = $(frm).serializeArray();

          // Get the URL
          targeturl = $(frm).attr("targeturl");

          // Double check
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  action = response['action'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else if (action !== undefined && action !== "") {
                    switch (action) {
                      case "deleted":
                      case "removed":
                        // $(elStart).css("color", "gray");
                        $(elStart).removeClass("sitem-button-selected");
                        $(elStart).addClass("sitem-button");
                        $(elStart).html('<span class="glyphicon glyphicon-star-empty"></span>');
                        $(elStart).attr("title", "Add to your saved items");
                        // Change the sitem action to be taken
                        $(frm).find("#id_sitemaction").val("add");
                        break;
                      case "added":
                        // $(elStart).css("color", "red");
                        $(elStart).removeClass("sitem-button");
                        $(elStart).addClass("sitem-button-selected");
                        $(elStart).html('<span class="glyphicon glyphicon-star"></span>');
                        $(elStart).attr("title", "Remove from your saved items");
                        // Change the sitem action to be taken
                        $(frm).find("#id_sitemaction").val("remove");
                        break;
                    }
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });


        } catch (ex) {
          private_methods.errMsg("do_saveditem", ex);
        }
      },

      /**
       * do_sgroup
       *    Add saved group, or cancel
       *
       */
      do_sgroup: function (elStart, sAction) {
        var targeturl = "",
            frm = null,
            data = null,
            table = null,
            action = "",
            elSgroup = null,
            sGroupNew = "",
            sGroupName = "";

        try {
          frm = $(elStart).closest("form");
          // Get the data
          data = $(frm).serializeArray();

          // Get the URL
          targeturl = $(frm).attr("targeturl");

          // Get the table
          table = $(elStart).closest(".related-original").find("table.func-view.related.sel-table").first();

          if (sAction === "add_sgroup") {

            // Double check
            $.post(targeturl, data, function (response) {
              // Action depends on the response
              if (response === undefined || response === null || !("status" in response)) {
                private_methods.errMsg("No status returned");
              } else {
                switch (response.status) {
                  case "ready":
                  case "ok":
                    // Should have a new target URL
                    targeturl = response['targeturl'];
                    action = response['action'];
                    if (targeturl !== undefined && targeturl !== "") {
                      // Go open that targeturl
                      window.location = targeturl;
                    } else if (action !== undefined && action !== "") {
                      switch (action) {
                        case "added":
                          // Hide the interface
                          $("#sgroup-add").addClass("collapse");
                          $("#sgroup-add").removeClass("in");
                          // Make sure that the savegroup name row is added to the table appropriately
                          sGroupNew = response['sgroupnew'];
                          // Add this to the table
                          $(table).find("tbody:last-child").append(sGroupNew);
                          break;
                      }
                    }
                    break;
                  case "error":
                    if ("html" in response) {
                      // Show the HTML in the targetid
                      $(err).html(response['html']);
                      // If there is an error, indicate this
                      if (response.status === "error") {
                        if ("msg" in response) {
                          if (typeof response['msg'] === "object") {
                            lHtml = []
                            lHtml.push("Errors:");
                            $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                            $(err).html(lHtml.join("<br />"));
                          } else {
                            $(err).html("Error: " + response['msg']);
                          }
                        } else {
                          $(err).html("<code>There is an error</code>");
                        }
                      }
                    } else {
                      // Send a message
                      $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                    }
                    break;
                  default:
                    // Something went wrong -- show the page or not?
                    $(err).html("The status returned is unknown: " + response.status);
                    break;
                }

              }
            });

          }



        } catch (ex) {
          private_methods.errMsg("do_sgroup", ex);
        }
      },

      /**
       * do_selitem
       *    Check or uncheck items for selection
       *
       */
      do_selitem: function (elStart, sAction) {
        var frm = null,
            targeturl = "",
            action = "",
            elTd = null,
            i = 0,
            elSelItemDct = "#selitem-dct",
            elSelItemRset = "#selitem-rset",
            err = "#little_err_msg",
            selitemcount = "",
            data = null;

        try {
          // Figure out what we are doing
          if ($(elSelItemDct).length === 0) {
            // Need to change this stuff
          }
          // In general: hide the -rset
          $(elSelItemRset).addClass("hidden");

          // Is this just canceling?
          switch (sAction) {
            case "cancel_dct":
              // This is just canceling the current idea of selecting a Research Set
              $(elSelItemDct).addClass("hidden");
              return;
            case "show_dct":
              // Make sure the researcher can select a Research Set
              $(elSelItemDct).removeClass("hidden");
              $(elSelItemRset).addClass("hidden");
              return;
          }

          // Get to the form
          if ($(elStart)[0].localName.toLowerCase() === "form") {
            frm = $(elStart);
          } else {
            frm = $(elStart).closest(".selitem").attr("targetid");
          }
          // Get the data
          data = $(frm).serializeArray();
          // Append the action to it
          data.push({name: "mode", value: sAction});

          // Find nearest <td>
          elTd = $(elStart).closest("td");

          // Get the URL
          targeturl = $(frm).attr("targeturl");

          // Double check
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  action = response['action'];
                  // Get selitemcount
                  selitemcount = response['selitemcount'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else if (action !== undefined && action !== "") {
                    switch (action) {
                      case "del_items":
                        // This just calls for re-loading the page
                        window.location = window.location;
                        break;
                      case "update_sav":
                        // Adapt all relevant material
                        $(".selitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("selitem-button-selected");
                          $(el).addClass("selitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_selitemaction").val("add");

                          // Make sure the SavedItem is showing
                          el = $(elTr).find(".sitem-button").first();
                          if (el.length > 0) {
                            $(el).find("span").removeClass("glyphicon-star-empty");
                            $(el).find("span").addClass("glyphicon-star");
                            $(el).removeClass("sitem-button");
                            $(el).addClass("sitem-button-selected");
                            // $(el).attr("onclick", 'ru.dct.do_saveditem(this, "add");');
                            $(el).attr("title", "Remove from your saved items");

                            $(el).unbind("click").on("click", function (evt) {
                              ru.dct.do_saveditem(elStart, "remove");
                            });
                            $(el).closest("td").find("#id_sitemaction").val("remove");
                          }
                        });

                        // Adapt selitemcount
                        selitemcount = 0;
                        break;
                      case "update_basket":
                        // Check if this is a new basket
                        if (response['newbasket'] !== undefined) {
                          frm = response['newbasket'];
                          $(frm).submit();
                        }
                        // Adapt all relevant material
                        $(".selitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("selitem-button-selected");
                          $(el).addClass("selitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_selitemaction").val("add");

                        });

                        // Make sure the Basket number is showing correctly
                        $("#basketsize").html("(" + response.basketsize + ")");

                        // Adapt selitemcount
                        selitemcount = 0;
                        break;
                      case "update_dct":
                        // Adapt all relevant material
                        $(".selitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("selitem-button-selected");
                          $(el).addClass("selitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_selitemaction").val("add");

                        });
                        // Adapt selitemcount
                        selitemcount = 0;
                        // Also make sure to close the selitem-dct
                        $(elSelItemDct).addClass("hidden");
                        $(elSelItemRset).find("a").first().attr("href", response.researchset);
                        $(elSelItemRset).removeClass("hidden");
                        break;
                      case "clear_sel":
                        // Adapt all relevant material
                        $(".selitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td");

                          // Change the class
                          $(el).removeClass("selitem-button-selected");
                          $(el).addClass("selitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_selitemaction").val("add");
                        });
                        break;
                      case "deleted":
                      case "removed":
                        $(elStart).removeClass("selitem-button-selected");
                        $(elStart).addClass("selitem-button");
                        $(elStart).html('<span class="glyphicon glyphicon-unchecked"></span>');
                        $(elStart).attr("title", "Select this item");
                        // Change the sitem action to be taken
                        $(elTd).find("#id_selitemaction").val("add");
                        break;
                      case "added":
                        // $(elStart).css("color", "red");
                        $(elStart).removeClass("selitem-button");
                        $(elStart).addClass("selitem-button-selected");
                        $(elStart).html('<span class="glyphicon glyphicon-check"></span>');
                        $(elStart).attr("title", "Uncheck this item");
                        // Change the sitem action to be taken
                        $(elTd).find("#id_selitemaction").val("remove");
                        break;
                    }
                    // Adapt the amount of selected items
                    if (selitemcount !== undefined) {
                      if (selitemcount <= 0) {
                        $(".selcount").html("");
                        $(".select-execute button").attr("disabled", true);
                      } else {
                        $(".selcount").html(selitemcount);
                        $(".select-execute button").attr("disabled", false);
                      }
                    }
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });


        } catch (ex) {
          private_methods.errMsg("do_selitem", ex);
        }
      },

      /**
       * init_selection
       *    Initialize selecting stuff
       *
       */
      init_selection: function () {
        try {
          // Visit every button under class 'select-execute'

          $(".select-execute button").each(function (idx, el) {
            var mode = $(el).attr("mode"),
                elStart = $(".selitem-main").first();

            $(el).unbind("click").on("click", function (evt) {
              ru.dct.do_selitem(elStart, mode);
            });
          });

        } catch (ex) {
          private_methods.errMsg("init_selection", ex);
        }
      },

      /**
       * load_dct
       *    Ask for the DCT definition using AJAX
       *
       */
      load_dct: function () {
        var data = [],
            frm = null,
            targeturl = "",
            contents = null,
            ssglists = null,
            params = null,
            view_mode = "",
            elDctId = "#dct_id";

        try {
          // Get the target URL
          targeturl = $(elDctId).attr("targeturl");
          // Get to the form
          frm = $(elDctId).closest("form");
          data = frm.serializeArray();

          // Sanity check
          if ($(elDctId).length === 0) {
            return;
          }

          // Get the data right now
          // Try to delete: send a POST
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Pick up and unpack the contents
                  contents = response['contents'];
                  ssglists = contents['ssglists'];
                  params = contents['params'];
                  // Make sure to also copy it to the local storage
                  loc_ssglists = ssglists;
                  loc_params = params;

                  // Get the view mode
                  view_mode = $("#viewmode").val();
                  params['view_mode'] = view_mode;

                  // If all is set, show it
                  if (loc_ssglists !== undefined && loc_ssglists != "" && loc_ssglists.length > 0) {
                    // show this DCT
                    private_methods.dct_show(loc_ssglists, params);

                    // Prepare copy
                    $(".dct-root").each(function (idx, el) {
                      var elOriginal = $(el).find(".dct-view").first(),
                          elCopy = $(el).find(".dct-copy").first(),
                          clone;

                      if (elOriginal.length > 0 && elCopy.length > 0) {
                        // Copy original to copy
                        $(elCopy).html($(elOriginal).html());

                      }
                    });

                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("load_dct", ex);
        }
      },

      /**
       * sel_button
       *    Show or hide the select column
       *
       */
      sel_button: function (elStart) {
        var elTable = null,
            elS = null,
            elH = null,
            elRelated = null,
            selcount = "",
            mode = "";

        try {
          // Find out which mode I am in
          mode = ($(elStart).hasClass("jumbo-1")) ? "hide" : "show";

          // Figure out what the selection count is
          selcount = $(".selcount").first().html().trim();

          // Find the table
          elTable = $("table.func-view").first();
          // Find the <h3> element
          elH = $(elStart).closest("h4");
          // Find the related container
          elRelated = $(elStart).closest(".related-original");
          // Either hide or show the .select-column
          switch (mode) {
            case "hide":
              // Turn into showing
              $(elTable).find(".select-column").removeClass("hidden");
              // Change the button into 'showing'
              $(elStart).removeClass("jumbo-1");
              $(elStart).addClass("jumbo-3");
              // Set proper execution button visibility
              $(elH).find(".select-execute").removeClass("hidden");

              // make sure .selcount changes correctly
              $(elRelated).find(".selcount").addClass("showing");

              // Should it be disabled or not?
              if (selcount === undefined || selcount === "") {
                $(elH).find(".select-execute button").attr("disabled", true);
              } else {
                $(elH).find(".select-execute button").attr("disabled", false);
              }
              // Set the correct 's' parameter
              elS = document.getElementsByName("s");
              $(elS).val("show");
              break;
            case "show":
              // Turn into hiding
              $(elTable).find(".select-column").addClass("hidden");
              // Change the button into 'hiding'
              $(elStart).removeClass("jumbo-3");
              $(elStart).addClass("jumbo-1");
              // Set proper execution button visibility
              $(elH).find(".select-execute").addClass("hidden");

              // make sure .selcount changes correctly
              $(elRelated).find(".selcount").removeClass("showing");

              // Should it be disabled or not?
              if (selcount === undefined || selcount === "") {
                $(elH).find(".select-execute button").attr("disabled", true);
              }
              // Set the correct 's' parameter
              elS = document.getElementsByName("s");
              $(elS).val("hide");
              break;
          }

        } catch (ex) {
          private_methods.errMsg("sel_button", ex);
        }
      },

      /**
       * show_dct
       *    Re-draw the DCT
       *
       */
      show_dct: function () {
        var params = null,
            view_mode = "",
            col_mode = "",
            bChanged = false;

        try {
          // Get the values
          params = loc_params;

          // Get the view mode and the column order
          view_mode = $("#viewmode").val();
          col_mode = $("#colmode").val();

          if (view_mode !== params['view_mode']) {
            params['view_mode'] = $("#viewmode").val();
            bChanged = true;
          }
          if (col_mode !== params['col_mode']) {
            params['col_mode'] = $("#colmode").val();
            bChanged = true;
          }

          // If all is set, show it
          if (loc_ssglists !== undefined && loc_ssglists != "" && loc_ssglists.length > 0) {
            // show this DCT
            private_methods.dct_show(loc_ssglists, params);
            // Any changes?
            if (bChanged) {
              // Make sure save buttons are shown
              private_methods.dct_saveshow();
            }
          }
        } catch (ex) {
          private_methods.errMsg("show_dct", ex);
        }
      },


      /**
       * do_importreview
       *    Request to process an ImportReview definition
       *
       */
      do_importreview: function (el, verdict) {
        var targetid = "",
          targeturl = "",
          reportid = "",
          data = null,
          err = "#import_err",
          frm = null;

        try {
          // Disable the Reject and Accept buttons
          $(el).closest("span").find("a").attr("disable", true);
          // Get the targeturl
          targetid = $(el).closest("span").attr("targetid");
          targeturl = $(targetid).attr("targeturl");
          err = targetid.replace("import_form", "import_err");

          // Get the form information
          frm = $(targetid).closest("form");
          // Get the data
          data = $(frm).serializeArray();
          // Add the import verdict
          data.push({ name: "importverdict", value: verdict });

          // Indicate that we are working
          $(err).html(loc_sWaiting);

          // Perform a POST request with this
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  $(err).html("");
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else {
                    // Tell user can't go anywhere
                    $(err).html("Sorry, I am missing the targeturl");
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });

        } catch (ex) {
          private_methods.errMsg("do_importreview", ex);
        }
      },

      /**
       * do_importset
       *    Request to process an ImportSet definition
       *
       */
      do_importset: function (el) {
        var targetid = "",
            targeturl = "",
            reportid = "",
            data = null,
            err = "#import_err",
            frm = null;

        try {
          // Disable the button
          $(el).attr("disable", true);
          // Get the targeturl
          targetid = $(el).closest("span").attr("targetid");
          targeturl = $(targetid).attr("targeturl");
          err = targetid.replace("import_form", "import_err");

          // Try to find the report
          reportid = $(el).closest("table").find("td span:contains('Report:')");
          if (reportid.length > 0) {
            reportid = $(reportid).closest("tr").find("td").last();
            if (reportid.length > 0) {
              $(reportid).html("verifying...");
            }
          }


          // Get the form information
          frm = $(targetid).closest("form");
          // Get the data
          data = $(frm).serializeArray();

          // Indicate that we are working
          $(err).html(loc_sWaiting);

          // Perform a POST request with this
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  $(err).html("");
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else {
                    // Tell user can't go anywhere
                    $(err).html("Sorry, I am missing the targeturl");
                  }
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });

        } catch (ex) {
          private_methods.errMsg("do_importset", ex);
        }
      },

      /**
       * postsubmit
       *    Submit nearest form as POST
       *
       */
      postsubmit: function (el) {
        var frm = null;

        try {
          frm = $(el).closest("form");
          // Make sure we do a POST
          frm.attr("method", "POST");
          // Submit
          $(frm).submit();
        } catch (ex) {
          private_methods.errMsg("postsubmit", ex);
        }
      }



      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

