"""Play-page body, extracted verbatim from the archived sportsgamesaz.io
2v2io page. build-archive.py substitutes the __TOKENS__ per game."""

PLAY_BODY = """\
<div class="GamePageDesktop_main__fSalE">
 <div class="GamePageDesktop_mainContainer__QMRhB" id="gamePageMainContainer">
  <div class="GamePageDesktop_gfContainer__ywzsh">
   <div class="GamePageDesktop_gfAspectRatioContainer__f_hUp">
    <div class="css-uwwqev">
     <div class="GameContainer" style="position: relative; width: 100%; height: 100%;">
      <iframe allowfullscreen="" border="0" class="d-block" data-embed="__EMBED__" frameborder="0" height="100%" id="game-iframe" scrolling="no" src="" style="border: 0px; margin: 0px; padding: 0px; width: 100%; height: 100%; position: absolute; top: 0px; left: 0px; user-select: none;" width="100%">
      </iframe>
     </div>
    </div>
    <div class="css-1h1938b">
     <div class="MuiGrid-root MuiGrid-container MuiGrid-wrap-xs-nowrap css-1xe247z">
      <div class="MuiGrid-root MuiGrid-item css-lhmnzp">
       <div class="css-glv0sd">
        <div class="css-inwm4l" style="margin-left:0">
         __TITLE__
        </div>
       </div>
      </div>
      <div class="MuiGrid-root MuiGrid-item css-u9enjd">
       <div class="MuiGrid-root MuiGrid-container MuiGrid-item MuiGrid-wrap-xs-nowrap css-1h1owej">
        <div style="display: inline-flex; gap: 2px;">
        </div>
        <div class="MuiGrid-root MuiGrid-item css-16hlm1x">
         <button class="MuiButtonBase-root MuiButton-root MuiButton-text MuiButton-textPrimary MuiButton-sizeMedium MuiButton-textSizeMedium MuiButton-colorPrimary MuiButton-root MuiButton-text MuiButton-textPrimary MuiButton-sizeMedium MuiButton-textSizeMedium MuiButton-colorPrimary footerButton css-1bnqyvi" data-content="Fullscreen" id="expand" tabindex="0" type="button">
          <svg aria-hidden="true" class="MuiSvgIcon-root MuiSvgIcon-fontSizeMedium css-14yq2cq svg-unactive" focusable="false" height="24" viewbox="0 0 24 24" width="24">
           <path clip-rule="evenodd" d="M4 2C2.89543 2 2 2.89543 2 4V8C2 8.55228 2.44772 9 3 9C3.55228 9 4 8.55228 4 8V5.41421L7.79289 9.20711C8.18342 9.59763 8.81658 9.59763 9.20711 9.20711C9.59763 8.81658 9.59763 8.18342 9.20711 7.79289L5.41421 4H8C8.55228 4 9 3.55228 9 3C9 2.44772 8.55228 2 8 2H4ZM16 2C15.4477 2 15 2.44772 15 3C15 3.55228 15.4477 4 16 4H18.5858L14.7929 7.79289C14.4024 8.18342 14.4024 8.81658 14.7929 9.20711C15.1834 9.59763 15.8166 9.59763 16.2071 9.20711L20 5.41421V8C20 8.55228 20.4477 9 21 9C21.5523 9 22 8.55228 22 8V4C22 2.89543 21.1046 2 20 2H16ZM16 20L18.5858 20L14.7929 16.2071C14.4024 15.8166 14.4024 15.1834 14.7929 14.7929C15.1834 14.4024 15.8166 14.4024 16.2071 14.7929L20 18.5858V16C20 15.4477 20.4477 15 21 15C21.5523 15 22 15.4477 22 16V20C22 21.1046 21.1046 22 20 22L16 22C15.4477 22 15 21.5523 15 21C15 20.4477 15.4477 20 16 20ZM4 18.5858L7.79289 14.7929C8.18342 14.4024 8.81658 14.4024 9.20711 14.7929C9.59763 15.1834 9.59763 15.8166 9.20711 16.2071L5.41421 20H8C8.55228 20 9 20.4477 9 21C9 21.5523 8.55228 22 8 22H4C2.89543 22 2 21.1046 2 20V16C2 15.4477 2.44772 15 3 15C3.55228 15 4 15.4477 4 16L4 18.5858Z" fill-rule="evenodd">
           </path>
          </svg>
          <svg aria-hidden="true" class="MuiSvgIcon-root MuiSvgIcon-fontSizeMedium css-14yq2cq svg-active" focusable="false" viewbox="0 0 24 24">
           <path clip-rule="evenodd" d="M17 18.4142L20.2929 21.7071C20.6834 22.0976 21.3166 22.0976 21.7071 21.7071C22.0976 21.3166 22.0976 20.6834 21.7071 20.2929L18.4142 17L21 17C21.5523 17 22 16.5523 22 16C22 15.4477 21.5523 15 21 15L17 15C15.8954 15 15 15.8954 15 17L15 21C15 21.5523 15.4477 22 16 22C16.5523 22 17 21.5523 17 21L17 18.4142ZM7 5.58578V3C7 2.44772 7.44772 2 8 2C8.55229 2 9 2.44772 9 3V7C9 8.10457 8.10457 9 7 9H3C2.44772 9 2 8.55229 2 8C2 7.44772 2.44772 7 3 7H5.58579L2.2929 3.70711C1.90237 3.31658 1.90237 2.68342 2.2929 2.29289C2.68342 1.90237 3.31659 1.90237 3.70711 2.29289L7 5.58578ZM21 9C21.5523 9 22 8.55229 22 8C22 7.44772 21.5523 7 21 7L18.4142 7L21.7071 3.70711C22.0976 3.31658 22.0976 2.68342 21.7071 2.2929C21.3166 1.90237 20.6834 1.90237 20.2929 2.2929L17 5.58579L17 3C17 2.44772 16.5523 2 16 2C15.4477 2 15 2.44772 15 3L15 7C15 8.10457 15.8954 9 17 9L21 9ZM3 15C2.44772 15 2 15.4477 2 16C2 16.5523 2.44772 17 3 17H5.58579L2.29289 20.2929C1.90237 20.6834 1.90237 21.3166 2.29289 21.7071C2.68342 22.0976 3.31658 22.0976 3.70711 21.7071L7 18.4142V21C7 21.5523 7.44772 22 8 22C8.55229 22 9 21.5523 9 21V17C9 15.8954 8.10457 15 7 15H3Z" fill-rule="evenodd" xmlns="http://www.w3.org/2000/svg">
           </path>
          </svg>
          <span class="MuiTouchRipple-root css-w0pj6f">
          </span>
         </button>
        </div>
       </div>
      </div>
     </div>
    </div>
   </div>
  </div>
  <div class="GamePageDesktop_underGameContainerGrid__cdhNC">
   <div class="GamePageDesktop_underGameContainerGamesWrapper__Rahgf">
    <div class="css-ujjn8y" id="cgMoreGrid" style="justify-content: center;">
    </div>
   </div>
  </div>
  <div class="GamePageDesktop_gameInfoContainer__SwKQu">
   <div class="GameInfo_gameInfo__2UItk GameInfo_isDesktop__KqJ3d">
    <div class="GameInfo_leftColumn__vMTeN">
     <!--$ads 728x90-->
     <div class="GameInfo_roundedCornersContainer__D5D_p" style="margin-top:12px;">
      <div class="Breadcrumbs_breadcrumbs__L3mrb">
       <div>
        <a href="./">
         Home
        </a>
        <div class="Breadcrumbs_separator__yCVN1">
         »
        </div>
       </div>
       <div>
        <span style="font-size:14px;">
         __TITLE__
        </span>
       </div>
      </div>
      <div class="GameInfo_containerWithPadding__z9aMp">
       <h1>
        __TITLE__
       </h1>
      </div>
      <div>
       <div class="GameSummary_gameTableRow__9i4Mt">
        <div class="GameSummary_gameTableRowHeader__qmvU_">
         Rating:
        </div>
        <div class="GameSummary_gameTableRowContent__RW5fE">
         __RATING__
        </div>
       </div>
      </div>
      <div class="GameTags_gameTagChipContainer__F5xPO">
       __TAGS__
      </div>
     </div>
     <div class="GameInfo_roundedCornersContainer__D5D_p">
      <div class="GameInfo_styledHtmlDiv__Zg2EY">
       __DESC__
      </div>
     </div>
    </div>
   </div>
  </div>
 </div>
 <div class="GamePageDesktop_rightSidebar__QgTMJ">
  <div class="GamePageDesktop_rightGridContainer__qJUvH">
   <div class="css-ujjn8y" id="cgSideList" style="justify-content: center;">
   </div>
  </div>
 </div>
 <div class="BackToTop_buttonContainer__GQast BackToTop_center__l50Lu BackToTop_hide__qS9u6">
  <button class="MuiButton-root BackToTop_jumpingButton__MI8to BackToTop_hasLabel__e_GhC BackToTop_isDesktop__QrI6d BackToTop_playAnimation__lIo7n css-1ii02y2" type="button">
   <svg aria-hidden="true" class="css-6qu7l6" focusable="false" viewbox="0 0 24 24">
    <path clip-rule="evenodd" d="M5.25759 8.33007C4.88759 8.7401 4.92005 9.37243 5.33007 9.74243C5.7401 10.1124 6.37243 10.08 6.74243 9.66994L11 4.95172L11 21C11 21.5523 11.4477 22 12 22C12.5523 22 13 21.5523 13 21L13 4.95171L17.2576 9.66994C17.6276 10.08 18.2599 10.1124 18.6699 9.74243C19.08 9.37243 19.1124 8.7401 18.7424 8.33007L13.7424 2.7891C12.793 1.73698 11.207 1.73697 10.2576 2.7891L5.25759 8.33007Z" fill-rule="evenodd">
    </path>
   </svg>
   Back to game
  </button>
 </div>
</div>
"""
